<script setup lang="ts">
// "/" has no content of its own: signed-in students land on Today, everyone else on the sign-in page.
// The global auth middleware performs the redirect before this component renders.
definePageMeta({ layout: false })
</script>

<template>
  <span class="sr-only">Redirecting…</span>
</template>
