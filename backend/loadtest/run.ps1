# Load test driver (docs/search.md, "Load testing"). From backend/, in PowerShell:
#   .\loadtest\run.ps1 -InDocker -Backends pg,es -Levels 10,25,50,75,100,250,500
# (not "powershell -File": that passes "10,25,..." as one string)
# Per backend: starts the API, warms it up, then per level: fresh tokens, resource sampler, one k6 run.
# -InDocker: the API runs as a Linux container (samaj-api:dev, `docker build -t samaj-api:dev .`) limited to
#   -ApiCpus cores, next to ES and postgres-test; k6 calls it over the Docker network. Use this for numbers:
#   uvicorn --workers is unreliable on Windows (worker processes fail with WinError 10022 and restart).
# Without it: uvicorn on this machine (loadtest/serve.py), k6 via host.docker.internal.
# Results: loadtest/.out/summary-<label>.json and samples-<label>.json; then python -m loadtest.report.
param(
    [string[]]$Backends = @("pg", "es"),
    [int[]]$Levels = @(10, 25, 50, 75, 100, 250, 500),
    [string]$Mix = "mixed",
    [string]$Duration = "45s",
    [int]$Workers = 4,
    [switch]$InDocker,
    [int]$ApiCpus = 4,
    [int]$Port = 8765,  # host port for the API; not 8000, which the dev API (or another project) may hold
    [string]$Tag = "",
    [int]$Churn = 0,           # renames per second during each level, with a search worker running (index lag)
    [int]$RestartEsAfter = 0,  # seconds into each level to restart the Elasticsearch container (outage test)
    [string]$IndexPrefix = "samaj_load"
)
Set-Location (Split-Path $PSScriptRoot)
# host-side tools (seed, sampler, worker, churn) use the throwaway test database, never production
$env:DATABASE_URL = "postgresql+psycopg2://samaj:samaj-test@127.0.0.1:5433/samaj"
$env:ELASTICSEARCH_INDEX_PREFIX = $IndexPrefix
$py = ".\venv\Scripts\python.exe"
$out = "loadtest\.out"
$net = "samaj-search_default"
$k6 = "grafana/k6:1.4.2"
New-Item -ItemType Directory -Force $out | Out-Null

function Start-Api($backend) {
    if ($InDocker) {
        docker rm -f samaj-load-api 2>&1 | Out-Null
        $esUrl = if ($backend -eq "pg") { "" } else { "http://elasticsearch:9200" }
        docker run -d --name samaj-load-api --network $net --cpus $ApiCpus -p "127.0.0.1:${Port}:8000" --env-file .env `
            -e "DATABASE_URL=postgresql+psycopg2://samaj:samaj-test@postgres-test:5432/samaj" `
            -e "ELASTICSEARCH_URL=$esUrl" -e "ELASTICSEARCH_INDEX_PREFIX=$IndexPrefix" -e SEARCH_RATE_PER_MINUTE=1000000 `
            samaj-api:dev uvicorn main:app --host 0.0.0.0 --port 8000 --workers $Workers --no-access-log | Out-Null
        return $null
    }
    return Start-Process $py -ArgumentList "-m", "loadtest.serve", $backend, $Workers, $Port -PassThru -WindowStyle Hidden
}

function Stop-Api($proc, $backend) {
    if ($InDocker) {
        docker logs samaj-load-api 2>&1 | Out-File -Encoding utf8 "$out\api-$Tag$backend.log"  # worker crashes, warnings
        docker rm -f samaj-load-api 2>&1 | Out-Null
    } else { taskkill /PID $proc.Id /T /F | Out-Null }
    Start-Sleep 3
}

function Invoke-K6($vus, $duration, $label) {
    $base = if ($InDocker) { "http://samaj-load-api:8000" } else { "http://host.docker.internal:$Port" }
    $network = if ($InDocker) { @("--network", $net) } else { @() }
    docker run --rm @network -v "${PWD}\loadtest:/scripts" -e BASE=$base -e VUS=$vus -e MIX=$Mix -e DURATION=$duration `
        -e LABEL=$label $k6 run --quiet /scripts/search.js 2>&1 | Out-Null
}

foreach ($b in $Backends) {
    $api = Start-Api $b
    $up = $false
    foreach ($i in 1..60) {
        Start-Sleep 1
        try { Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2 | Out-Null; $up = $true; break } catch {}
    }
    if (-not $up) { Stop-Api $api $b; throw "API did not start" }
    try {
        # warm-up, not recorded: every worker opens its DB and ES connections and Postgres/ES warm their caches
        & $py -m loadtest.seed --tokens 1000 | Out-Null
        Invoke-K6 20 "10s" "warmup"
        foreach ($vus in $Levels) {
            $label = "$Tag$b-$Mix-$vus"
            & $py -m loadtest.seed --tokens 1000 | Out-Null
            $target = if ($InDocker) { "samaj-load-api" } else { "$Port" }
            $sampler = Start-Process $py -ArgumentList "-m", "loadtest.sample", $label, $target -PassThru -WindowStyle Hidden
            $extra = @()
            if ($Churn -gt 0) {
                $extra += Start-Process $py -ArgumentList "-m", "search.worker" -PassThru -WindowStyle Hidden
                $extra += Start-Process $py -ArgumentList "-m", "loadtest.churn", ([int]$Duration.TrimEnd("s")), $Churn `
                    -PassThru -WindowStyle Hidden
            }
            if ($RestartEsAfter -gt 0) {
                $restart = Start-Job { Start-Sleep $using:RestartEsAfter; docker restart samaj-search-elasticsearch-1 }
            }
            Invoke-K6 $vus $Duration $label
            New-Item -ItemType File "$out\stop-$label" -Force | Out-Null
            $sampler.WaitForExit()
            foreach ($p in $extra) { taskkill /PID $p.Id /T /F 2>&1 | Out-Null }
            if ($RestartEsAfter -gt 0) { Wait-Job $restart | Out-Null; Remove-Job $restart }
            Write-Output "$label done"
        }
    } finally {
        Stop-Api $api $b
    }
}
