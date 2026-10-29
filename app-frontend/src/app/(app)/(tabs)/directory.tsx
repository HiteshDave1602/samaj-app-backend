import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Linking, Pressable, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Chips, Field, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api } from '@/lib/api';
import { label, loc, useT } from '@/lib/i18n';

// backend member/directory/schema.py DirectoryEntry
type Entry = {
  kind: 'MEMBER' | 'RELATIVE';
  id: string;
  full_name: string | null;
  full_name_i18n: Record<string, string>;
  relationship: string | null;
  household_id: string | null;
  family_name: string | null;
  family_name_i18n: Record<string, string>;
  native_place: string | null;
  native_place_i18n: Record<string, string>;
  city_name: string;
  city_name_i18n: Record<string, string>;
  phone: string | null;
  phone_hidden: boolean;
};
type City = { city_id: string; name: string; name_i18n: Record<string, string> };

// the backend needs 2+ characters for text filters; shorter input means "no filter"
const text = (s: string) => (s.trim().length >= 2 ? s.trim() : undefined);

// ponytail: first 50 results only; page with next_offset when directories get bigger
export default function DirectoryScreen() {
  const t = useT();
  const [query, setQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [cities, setCities] = useState<City[]>([]);
  const [city, setCity] = useState<string>();
  const [family, setFamily] = useState('');
  const [results, setResults] = useState<Entry[]>();
  const [error, setError] = useState<string>();
  const [bookmarks, setBookmarks] = useState(new Set<string>());
  const activeFilters = [city, text(family)].filter(Boolean).length;

  useEffect(() => {
    api<City[]>('/member/auth/cities').then(setCities, () => {});
  }, []);

  const cityId = cities.find((c) => loc(c.name, c.name_i18n) === city)?.city_id;
  const name = text(query);
  const familyName = text(family);
  useEffect(() => {
    const params = new URLSearchParams({ limit: '50' });
    if (name) params.set('name', name);
    if (familyName) params.set('family_name', familyName);
    if (cityId) params.set('city_id', cityId);
    // wait for typing to pause before asking the server
    const timer = setTimeout(
      () =>
        api<{ items: Entry[] }>(`/member/directory?${params}`).then(
          (r) => (setResults(r.items), setError(undefined)),
          (e) => setError(e.message),
        ),
      300,
    );
    return () => clearTimeout(timer);
  }, [name, familyName, cityId]);

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader title="Directory" />

      <View className="flex-row gap-2 px-5">
        <View className="h-12 flex-1 flex-row items-center gap-2 rounded-full border border-line bg-white px-4">
          <SymbolView name={{ ios: 'magnifyingglass', android: 'search', web: 'search' }} size={20} tintColor={Palette.muted} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder={t('Search by name')}
            placeholderTextColor={Palette.muted}
            accessibilityLabel={t('Search members')}
            returnKeyType="search"
            className="flex-1 font-inter text-base text-ink"
          />
        </View>
        <Pressable
          onPress={() => setShowFilters(!showFilters)}
          accessibilityRole="button"
          accessibilityLabel={t('Filters')}
          accessibilityState={{ expanded: showFilters }}
          className={`h-12 w-12 items-center justify-center rounded-full ${showFilters || activeFilters ? 'bg-primary' : 'border border-line bg-white'}`}>
          <SymbolView
            name={{ ios: 'line.3.horizontal.decrease', android: 'tune', web: 'tune' }}
            size={20}
            tintColor={showFilters || activeFilters ? '#FFFFFF' : Palette.ink}
          />
          {activeFilters > 0 && (
            <View className="absolute -right-0.5 -top-0.5 h-5 w-5 items-center justify-center rounded-full border-2 border-cream bg-accent">
              <Text className="font-inter-semibold text-[10px] text-ink">{activeFilters}</Text>
            </View>
          )}
        </Pressable>
      </View>

      {showFilters && (
        <View className="mx-5 mt-3 gap-4 rounded-3xl border border-line bg-white p-4">
          {/* tapping the selected chip again clears it */}
          <Chips label="City" options={cities.map((c) => loc(c.name, c.name_i18n)!)} value={city} onChange={(v) => setCity(v === city ? undefined : v)} />
          <Field label="Family name" value={family} onChangeText={setFamily} placeholder="e.g. Patel" />
          {activeFilters > 0 && (
            <Pressable
              onPress={() => {
                setCity(undefined);
                setFamily('');
              }}
              accessibilityRole="button"
              className="self-start">
              <Text className="font-inter-semibold text-sm text-primary">{t('Clear filters')}</Text>
            </Pressable>
          )}
        </View>
      )}

      <FlatList
        data={results}
        keyExtractor={(m) => m.id}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: 20, gap: 12 }}
        ListHeaderComponent={
          error ? (
            <Notice title="Could not load the directory" body={error} tone={Palette.rejected} />
          ) : results ? (
            <Text className="font-inter text-sm text-muted">
              {t(results.length === 1 ? '{n} person' : '{n} people', { n: results.length })}
            </Text>
          ) : (
            <ActivityIndicator color={Palette.primary.DEFAULT} />
          )
        }
        ListEmptyComponent={
          results && (
            <View className="items-center py-16">
              <Text className="font-inter-semibold text-base text-ink">{t('No members found')}</Text>
              <Text className="mt-1 font-inter text-sm text-muted">{t('Try another name or clear the filters.')}</Text>
            </View>
          )
        }
        renderItem={({ item }) => {
          const m = { ...item, name: loc(item.full_name, item.full_name_i18n) ?? t('Member'), city_name: loc(item.city_name, item.city_name_i18n) };
          const saved = bookmarks.has(m.id);
          const phone = m.phone?.replace(/\D/g, '');
          const family = [loc(m.family_name, m.family_name_i18n), loc(m.native_place, m.native_place_i18n)].filter(Boolean).join(' · ');
          return (
            <View className="rounded-3xl border border-line bg-white p-4 shadow-sm">
              <View className="flex-row gap-3">
                <View>
                  <Avatar name={m.name} size={64} tone={Palette.primary} />
                  {/* everyone listed here is ACTIVE, i.e. admin-verified */}
                  <View className="absolute -bottom-0.5 -right-0.5 rounded-full bg-white p-0.5">
                    <SymbolView
                      name={{ ios: 'checkmark.seal.fill', android: 'verified', web: 'verified' }}
                      size={20}
                      tintColor={Palette.primary.DEFAULT}
                    />
                  </View>
                </View>
                <View className="flex-1">
                  <View className="flex-row flex-wrap items-center gap-2">
                    <Text className="font-inter-semibold text-lg text-ink">{m.name}</Text>
                    <View className="rounded-full bg-primary-container px-2.5 py-0.5">
                      <Text className="font-inter-medium text-xs text-primary">{m.city_name}</Text>
                    </View>
                  </View>
                  {m.relationship && (
                    <Text numberOfLines={1} className="mt-0.5 font-inter text-sm text-subtle">
                      {t('{relation} of the family head', { relation: label(m.relationship) })}
                    </Text>
                  )}
                  {family !== '' && (
                    <View className="mt-1.5 flex-row items-center gap-1.5">
                      <SymbolView
                        name={{ ios: 'person.2.fill', android: 'family_restroom', web: 'family_restroom' }}
                        size={16}
                        tintColor={Palette.subtle}
                      />
                      <Text className="font-inter text-xs text-subtle">{family}</Text>
                    </View>
                  )}
                </View>
                {/* ponytail: bookmarks live in screen state; persist once a saved-members API exists */}
                <Pressable
                  onPress={() => {
                    const next = new Set(bookmarks);
                    if (saved) next.delete(m.id);
                    else next.add(m.id);
                    setBookmarks(next);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={t(saved ? 'Remove {name} from saved' : 'Save {name}', { name: m.name })}
                  accessibilityState={{ selected: saved }}
                  hitSlop={8}
                  className="self-start">
                  <SymbolView
                    name={{ ios: saved ? 'bookmark.fill' : 'bookmark', android: 'bookmark', web: 'bookmark' }}
                    size={24}
                    tintColor={saved ? Palette.primary.DEFAULT : Palette.ink}
                  />
                </Pressable>
              </View>

              <View className="my-3 h-px bg-line" />

              <View className="flex-row items-center gap-2">
                {/* members who chose hide_phone, and relatives (no contact details), get no call or WhatsApp buttons */}
                {m.phone_hidden && <Text className="font-inter text-sm text-muted">{t('Phone hidden')}</Text>}
                {phone && (
                  <>
                    <Pressable
                      onPress={() => Linking.openURL(`tel:+${phone}`)}
                      accessibilityRole="button"
                      accessibilityLabel={t('Call {name}', { name: m.name })}
                      className="h-10 flex-row items-center gap-1.5 rounded-full bg-surface px-4 active:opacity-80">
                      <SymbolView name={{ ios: 'phone', android: 'call', web: 'call' }} size={18} tintColor={Palette.primary.DEFAULT} />
                      <Text className="font-inter-medium text-sm text-ink">{t('Call')}</Text>
                    </Pressable>
                    <Pressable
                      onPress={() => Linking.openURL(`https://wa.me/${phone}`)}
                      accessibilityRole="button"
                      accessibilityLabel={`WhatsApp ${m.name}`}
                      className="h-10 flex-row items-center gap-1.5 rounded-full bg-surface px-4 active:opacity-80">
                      <SymbolView name={{ ios: 'message', android: 'chat', web: 'chat' }} size={18} tintColor={Palette.primary.DEFAULT} />
                      <Text className="font-inter-medium text-sm text-ink">WhatsApp</Text>
                    </Pressable>
                  </>
                )}
                {m.household_id && (
                <Pressable
                  onPress={() => router.push({ pathname: '/directory/[id]', params: { id: m.household_id! } })}
                  accessibilityRole="button"
                  accessibilityLabel={t("View {name}'s family", { name: m.name })}
                  className="ml-auto h-10 flex-row items-center gap-1 rounded-full bg-primary-container pl-4 pr-3 active:opacity-80">
                  <Text className="font-inter-semibold text-sm text-primary">{t('View Family')}</Text>
                  <SymbolView
                    name={{ ios: 'chevron.right', android: 'chevron_right', web: 'chevron_right' }}
                    size={16}
                    tintColor={Palette.primary.DEFAULT}
                  />
                </Pressable>
                )}
              </View>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}
