<template>
  <div class="relative min-h-dvh overflow-hidden">
    <div class="pointer-events-none absolute -top-40 -right-32 size-[34rem] rounded-full bg-brand/10 blur-3xl" aria-hidden="true" />
    <div class="pointer-events-none absolute -bottom-48 -left-24 size-[30rem] rounded-full bg-accent/10 blur-3xl" aria-hidden="true" />
    <div class="relative">
      <slot />
    </div>
  </div>
</template>
