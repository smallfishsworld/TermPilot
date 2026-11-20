<script setup lang="ts">
import { Check } from '@lucide/vue'
import type { Task } from '~/types/api'
import { formatDateTime, relativeTime } from '~/utils/format'

const props = defineProps<{ task: Task, overdue?: boolean }>()
defineEmits<{ toggle: [task: Task] }>()

const urgent = computed(() => !props.task.done && new Date(props.task.due_at).getTime() - Date.now() < 24 * 3600_000)
</script>

<template>
  <li class="flex items-start gap-3 py-2.5">
    <button
      class="mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border transition"
      :class="task.done ? 'border-ok bg-ok text-white dark:text-page' : 'border-line hover:border-brand'"
      :aria-label="task.done ? `Mark ${task.title} as not done` : `Mark ${task.title} as done`"
      @click="$emit('toggle', task)"
    >
      <Check v-if="task.done" class="size-3.5" />
    </button>
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm font-medium" :class="task.done ? 'text-muted line-through' : ''">{{ task.title }}</p>
      <p class="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
        <span v-if="task.course" class="truncate">{{ task.course }}</span>
        <span :title="formatDateTime(task.due_at)" :class="overdue ? 'text-danger' : urgent ? 'text-warn' : ''">
          {{ overdue ? 'was due' : 'due' }} {{ relativeTime(task.due_at) }}
        </span>
      </p>
    </div>
    <UiBadge v-if="task.category === 'exam'" tone="accent">exam</UiBadge>
    <UiBadge v-else-if="task.priority === 'high'" tone="warn">high</UiBadge>
  </li>
</template>
