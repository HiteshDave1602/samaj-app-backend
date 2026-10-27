import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { FlatList, Linking, Pressable, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Chips, ScreenHeader } from '@/components/ui/form';
import { MEMBERS } from '@/constants/sample-data';
import { Palette } from '@/constants/theme';

// ponytail: filters and search run on the client; move them to query params once the directory API pages results
const APPROVED = MEMBERS.filter((m) => m.status === 'ACTIVE');
const unique = (k: 'city' | 'gotra') => [...new Set(APPROVED.map((m) => m[k]))].sort();
const CITIES = unique('city');
const GOTRAS = unique('gotra');
const GENDERS = ['Male', 'Female'] as const;

export default function DirectoryScreen() {
  const [query, setQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [city, setCity] = useState<string>();
  const [gotra, setGotra] = useState<string>();
  const [gender, setGender] = useState<(typeof GENDERS)[number]>();
  const [bookmarks, setBookmarks] = useState(new Set<string>());
  const activeFilters = [city, gotra, gender].filter(Boolean).length;
  // tapping the selected chip again clears it
  const toggle = <T,>(set: (v: T | undefined) => void, cur: T | undefined) => (v: T) => set(v === cur ? undefined : v);

  const q = query.trim().toLowerCase();
  const results = APPROVED.filter(
    (m) =>
      (!q || [m.name, m.city, m.gotra, m.profession].some((f) => f.toLowerCase().includes(q))) &&
      (!city || m.city === city) &&
      (!gotra || m.gotra === gotra) &&
      (!gender || m.gender === gender),
  );

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader title="Directory" />

      <View className="flex-row gap-2 px-5">
        <View className="h-12 flex-1 flex-row items-center gap-2 rounded-full border border-line bg-white px-4">
          <SymbolView name={{ ios: 'magnifyingglass', android: 'search', web: 'search' }} size={20} tintColor={Palette.muted} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search name, city, gotra, profession"
            placeholderTextColor={Palette.muted}
            accessibilityLabel="Search members"
            returnKeyType="search"
            className="flex-1 font-inter text-base text-ink"
          />
        </View>
        <Pressable
          onPress={() => setShowFilters(!showFilters)}
          accessibilityRole="button"
          accessibilityLabel="Filters"
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
          <Chips label="City" options={CITIES} value={city} onChange={toggle(setCity, city)} />
          <Chips label="Gotra" options={GOTRAS} value={gotra} onChange={toggle(setGotra, gotra)} />
          <Chips label="Gender" options={GENDERS} value={gender} onChange={toggle(setGender, gender)} />
          {activeFilters > 0 && (
            <Pressable
              onPress={() => {
                setCity(undefined);
                setGotra(undefined);
                setGender(undefined);
              }}
              accessibilityRole="button"
              className="self-start">
              <Text className="font-inter-semibold text-sm text-primary">Clear filters</Text>
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
          <Text className="font-inter text-sm text-muted">
            {results.length} {results.length === 1 ? 'member' : 'members'}
          </Text>
        }
        ListEmptyComponent={
          <View className="items-center py-16">
            <Text className="font-inter-semibold text-base text-ink">No members found</Text>
            <Text className="mt-1 font-inter text-sm text-muted">Try another name or clear the filters.</Text>
          </View>
        }
        renderItem={({ item: m }) => {
          const saved = bookmarks.has(m.id);
          const phone = m.phone.replace(/\D/g, '');
          return (
            <View className="rounded-3xl border border-line bg-white p-4 shadow-sm">
              <View className="flex-row gap-3">
                <View>
                  <Avatar name={m.name} size={64} tone={Palette.secondary} />
                  {/* everyone listed here is ACTIVE, i.e. admin-verified */}
                  <View className="absolute -bottom-0.5 -right-0.5 rounded-full bg-white p-0.5">
                    <SymbolView
                      name={{ ios: 'checkmark.seal.fill', android: 'verified', web: 'verified' }}
                      size={20}
                      tintColor={Palette.secondary.DEFAULT}
                    />
                  </View>
                </View>
                <View className="flex-1">
                  <View className="flex-row flex-wrap items-center gap-2">
                    <Text className="font-inter-semibold text-lg text-ink">{m.name}</Text>
                    <View className="rounded-full bg-secondary-container px-2.5 py-0.5">
                      <Text className="font-inter-medium text-xs text-secondary">{m.city}</Text>
                    </View>
                  </View>
                  <Text numberOfLines={1} className="mt-0.5 font-inter text-sm text-subtle">
                    {m.profession}
                  </Text>
                  <View className="mt-1.5 flex-row items-center gap-1.5">
                    <SymbolView
                      name={{ ios: 'person.2.fill', android: 'family_restroom', web: 'family_restroom' }}
                      size={16}
                      tintColor={Palette.subtle}
                    />
                    <Text className="font-inter text-xs text-subtle">Gotra: {m.gotra}</Text>
                  </View>
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
                  accessibilityLabel={saved ? `Remove ${m.name} from saved` : `Save ${m.name}`}
                  accessibilityState={{ selected: saved }}
                  hitSlop={8}
                  className="self-start">
                  <SymbolView
                    name={{ ios: saved ? 'bookmark.fill' : 'bookmark', android: 'bookmark', web: 'bookmark' }}
                    size={24}
                    tintColor={saved ? Palette.secondary.DEFAULT : Palette.ink}
                  />
                </Pressable>
              </View>

              <View className="my-3 h-px bg-line" />

              <View className="flex-row items-center gap-2">
                {/* members who chose hide_phone don't get call or WhatsApp buttons */}
                {!m.hidePhone && (
                  <>
                    <Pressable
                      onPress={() => Linking.openURL(`tel:+${phone}`)}
                      accessibilityRole="button"
                      accessibilityLabel={`Call ${m.name}`}
                      className="h-10 flex-row items-center gap-1.5 rounded-full bg-surface px-4 active:opacity-80">
                      <SymbolView name={{ ios: 'phone', android: 'call', web: 'call' }} size={18} tintColor={Palette.secondary.DEFAULT} />
                      <Text className="font-inter-medium text-sm text-ink">Call</Text>
                    </Pressable>
                    <Pressable
                      onPress={() => Linking.openURL(`https://wa.me/${phone}`)}
                      accessibilityRole="button"
                      accessibilityLabel={`WhatsApp ${m.name}`}
                      className="h-10 flex-row items-center gap-1.5 rounded-full bg-surface px-4 active:opacity-80">
                      <SymbolView name={{ ios: 'message', android: 'chat', web: 'chat' }} size={18} tintColor={Palette.secondary.DEFAULT} />
                      <Text className="font-inter-medium text-sm text-ink">WhatsApp</Text>
                    </Pressable>
                  </>
                )}
                {/* ponytail: no member family screen yet; wire to a route once the family API is public */}
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`View ${m.name}'s family`}
                  className="ml-auto h-10 flex-row items-center gap-1 rounded-full bg-secondary-container pl-4 pr-3 active:opacity-80">
                  <Text className="font-inter-semibold text-sm text-secondary">View Family</Text>
                  <SymbolView
                    name={{ ios: 'chevron.right', android: 'chevron_right', web: 'chevron_right' }}
                    size={16}
                    tintColor={Palette.secondary.DEFAULT}
                  />
                </Pressable>
              </View>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}
