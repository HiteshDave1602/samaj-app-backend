import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

// ponytail: stand-in for tab screens not built yet; delete once each real screen lands
export function ComingSoon({ title }: { title: string }) {
  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <View className="flex-1 items-center justify-center px-8">
        <Text className="font-headline text-3xl text-brand">{title}</Text>
        <Text className="mt-2 font-inter text-base text-subtle">Coming soon</Text>
      </View>
    </SafeAreaView>
  );
}
