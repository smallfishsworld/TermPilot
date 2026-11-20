<script setup lang="ts">
import { useColorMode } from '@vueuse/core'

// Applies the stored light/dark preference (class "dark" on <html>).
useColorMode({ storageKey: 'termpilot.theme', initialValue: 'auto' })
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <AppToasts />
</template>
