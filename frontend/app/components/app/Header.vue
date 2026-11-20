<script setup lang="ts">
import { useColorMode } from '@vueuse/core'
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuRoot, DropdownMenuSeparator, DropdownMenuTrigger } from 'reka-ui'
import {
  BookOpenText, CalendarRange, GraduationCap, House, ListChecks, LogOut, Mail, Menu, Moon, RefreshCw, Settings, Sparkles, Sun, X,
} from '@lucide/vue'
import { useCampusStore } from '~/stores/campus'
import { useSessionStore } from '~/stores/session'
import { useToasts } from '~/stores/toasts'

const session = useSessionStore()
const campus = useCampusStore()
const toasts = useToasts()
const route = useRoute()
const mode = useColorMode({ storageKey: 'termpilot.theme', initialValue: 'auto' })
const mobileOpen = ref(false)

const links = [
  { to: '/today', label: 'Today', icon: House },
  { to: '/timetable', label: 'Timetable', icon: CalendarRange },
  { to: '/tasks', label: 'Tasks', icon: ListChecks },
  { to: '/assistant', label: 'Assistant', icon: Sparkles },
  { to: '/library', label: 'Library', icon: BookOpenText },
  { to: '/mail', label: 'Mail', icon: Mail },
  { to: '/academics', label: 'Academics', icon: GraduationCap },
]

const initials = computed(() =>
  (session.student?.display_name ?? '?').split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase(),
)

watch(() => route.path, () => { mobileOpen.value = false })

async function syncNow() {
  try {
    const run = await campus.sync()
    const failed = run.steps.filter(step => !step.ok)
    if (!failed.length) toasts.success('Everything is up to date.')
    else toasts.failure(new Error(`${failed.length} of ${run.steps.length} sources failed: ${failed[0]!.message}`))
    await refreshNuxtData()
    window.dispatchEvent(new CustomEvent('termpilot:synced'))
  }
  catch (error) {
    toasts.failure(error)
  }
}

function toggleTheme() {
  mode.value = mode.value === 'dark' ? 'light' : 'dark'
}
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-line bg-surface/85 backdrop-blur">
    <div class="mx-auto flex h-14 w-full max-w-[1400px] items-center gap-4 px-4 sm:px-6">
      <NuxtLink to="/today" class="shrink-0"><AppBrand /></NuxtLink>

      <nav class="ml-4 hidden items-center gap-1 lg:flex" aria-label="Main">
        <NuxtLink
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-muted transition hover:bg-surface-muted hover:text-ink"
          active-class="!bg-brand-soft !text-brand-strong font-medium"
        >
          <component :is="link.icon" class="size-4" />
          {{ link.label }}
        </NuxtLink>
      </nav>

      <div class="ml-auto flex items-center gap-1">
        <UiButton variant="ghost" size="sm" :loading="campus.syncing" title="Import the latest data from campus systems" @click="syncNow">
          <RefreshCw v-if="!campus.syncing" class="size-4" />
          <span class="hidden sm:inline">Sync</span>
        </UiButton>
        <UiButton variant="ghost" size="sm" :title="mode === 'dark' ? 'Light theme' : 'Dark theme'" @click="toggleTheme">
          <Sun v-if="mode === 'dark'" class="size-4" />
          <Moon v-else class="size-4" />
        </UiButton>

        <DropdownMenuRoot>
          <DropdownMenuTrigger class="ml-1 grid size-8 place-items-center rounded-full bg-brand text-xs font-semibold text-white dark:text-page" aria-label="Account menu">
            {{ initials }}
          </DropdownMenuTrigger>
          <DropdownMenuPortal>
            <DropdownMenuContent align="end" :side-offset="8" class="panel z-50 min-w-52 p-1 shadow-lg">
              <div class="px-3 py-2">
                <p class="text-sm font-medium">{{ session.student?.display_name }}</p>
                <p class="text-xs text-muted">{{ session.student?.department ?? 'Student' }}</p>
              </div>
              <DropdownMenuSeparator class="my-1 h-px bg-line" />
              <DropdownMenuItem class="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm outline-none data-[highlighted]:bg-surface-muted" @select="navigateTo('/settings')">
                <Settings class="size-4 text-muted" /> Settings
              </DropdownMenuItem>
              <DropdownMenuItem class="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm text-danger outline-none data-[highlighted]:bg-danger-soft" @select="session.signOut()">
                <LogOut class="size-4" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenuPortal>
        </DropdownMenuRoot>

        <UiButton variant="ghost" size="sm" class="lg:hidden" aria-label="Open navigation" @click="mobileOpen = !mobileOpen">
          <X v-if="mobileOpen" class="size-5" />
          <Menu v-else class="size-5" />
        </UiButton>
      </div>
    </div>

    <nav v-if="mobileOpen" class="grid grid-cols-2 gap-1 border-t border-line px-4 py-3 lg:hidden" aria-label="Main">
      <NuxtLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-muted"
        active-class="!bg-brand-soft !text-brand-strong font-medium"
      >
        <component :is="link.icon" class="size-4" /> {{ link.label }}
      </NuxtLink>
    </nav>
  </header>
</template>
