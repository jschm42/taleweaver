<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Crown, Eye, EyeOff, User } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiRadioCards from '@/components/ui/UiRadioCards.vue'
import UserKeyPolicyEditor from './UserKeyPolicyEditor.vue'

const props = defineProps<{
  isOpen: boolean
  isEditingExisting: boolean
  user: any
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', user: any): void
}>()

const editingUser = ref({ ...props.user })
const showPassword = ref(false)
const touched = ref(false)

watch(() => props.user, (newUser) => {
  editingUser.value = { ...newUser }
  showPassword.value = false
  touched.value = false
}, { deep: true })

const ROLE_OPTIONS = [
  { value: 'user', label: 'Player', description: 'Plays adventures and creates their own.', icon: User },
  { value: 'admin', label: 'Admin', description: 'Full access to AI settings, catalogs and users.', icon: Crown },
]

const usernameError = computed(() => {
  if (!touched.value) return null
  const name = editingUser.value.username?.trim() ?? ''
  if (!name) return 'A username is required.'
  return name.length < 3 ? 'At least 3 characters.' : null
})

const passwordError = computed(() =>
  touched.value && !props.isEditingExisting && !editingUser.value.password ? 'A password is required.' : null,
)

const handleSubmit = () => {
  touched.value = true
  if (usernameError.value || passwordError.value) return
  emit('save', editingUser.value)
}

function handleOpenChange(open: boolean): void {
  if (!open) emit('close')
}
</script>

<template>
  <UiModal
    :open="isOpen"
    :title="isEditingExisting ? 'Edit user' : 'Add user'"
    description="Account credentials and role."
    :persistent="isSubmitting"
    @update:open="handleOpenChange"
  >
    <form id="user-edit-form" class="space-y-5" novalidate @submit.prevent="handleSubmit">
      <UiField label="Username" required :error="usernameError">
        <UiInput v-model="editingUser.username" placeholder="e.g. Jean" autocomplete="off" data-autofocus />
      </UiField>

      <UiField
        :label="isEditingExisting ? 'New password' : 'Password'"
        :hint="isEditingExisting ? 'Leave empty to keep the current password.' : ''"
        :required="!isEditingExisting"
        :error="passwordError"
      >
        <div class="relative">
          <UiInput
            v-model="editingUser.password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="new-password"
            class="pr-10 wb-mono"
          />
          <UiIconButton
            :icon="showPassword ? EyeOff : Eye"
            :label="showPassword ? 'Hide password' : 'Show password'"
            size="sm"
            class="absolute right-1 top-1/2 -translate-y-1/2"
            @click="showPassword = !showPassword"
          />
        </div>
      </UiField>

      <UiField label="Role">
        <UiRadioCards v-model="editingUser.role" :options="ROLE_OPTIONS" label="Role" />
      </UiField>

      <UserKeyPolicyEditor
        v-if="isEditingExisting && editingUser.id"
        :key="editingUser.id"
        :user-id="editingUser.id"
        :overrides="editingUser.api_key_policy_overrides"
        :personal-key-providers="editingUser.personal_key_providers"
      />
    </form>

    <template #footer>
      <UiButton :disabled="isSubmitting" @click="emit('close')">Cancel</UiButton>
      <UiButton variant="primary" type="submit" form="user-edit-form" :loading="isSubmitting">
        {{ isEditingExisting ? 'Save user' : 'Add user' }}
      </UiButton>
    </template>
  </UiModal>
</template>
