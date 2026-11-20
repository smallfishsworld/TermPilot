<script setup lang="ts">
import { SwitchRoot, SwitchThumb } from 'reka-ui'

defineProps<{ label: string }>()
const model = defineModel<boolean>({ default: false })
</script>

<template>
  <label class="inline-flex cursor-pointer items-center gap-2 text-xs text-muted select-none">
    <SwitchRoot
      v-model="model"
      class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-line bg-surface-muted transition data-[state=checked]:border-brand data-[state=checked]:bg-brand"
    >
      <SwitchThumb class="block size-3.5 translate-x-0.5 rounded-full bg-white shadow transition data-[state=checked]:translate-x-[1.15rem]" />
    </SwitchRoot>
    {{ label }}
  </label>
</template>
