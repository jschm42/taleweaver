import { ref } from 'vue'
import { api } from '@/composables/useApi'

/**
 * UserService manages user administration operations:
 * - Fetching user list
 * - Creating new users
 * - Updating existing users
 * - Deleting users
 *
 * All user operations are persisted to the backend. The service maintains
 * the current list of users and provides status messages for operations.
 */
class UserService {
  // ============ STATE ============
  usersList = ref<any[]>([])
  isSubmitting = ref(false)
  statusMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null)

  // ============ FETCHING & CRUD OPERATIONS ============

  /**
   * Fetch the list of all users from the backend.
   */
  async fetchUsers() {
    try {
      this.usersList.value = await api.listUsers()
    } catch (error) {
      console.error('[UserService] Failed to fetch users:', error)
      this.statusMessage.value = { type: 'error', text: 'Failed to load users.' }
    }
  }

  /**
   * Create a new user in the system.
   * Validates that username is not empty.
   */
  async createUser(userData: any) {
    if (!userData.username?.trim()) {
      this.statusMessage.value = { type: 'error', text: 'Username is required.' }
      return
    }

    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      await api.createUser(userData)
      this.statusMessage.value = { type: 'success', text: 'User created.' }
      await this.fetchUsers()
    } catch (err: any) {
      console.error('[UserService] Failed to create user:', err)
      this.statusMessage.value = { type: 'error', text: 'Failed to create user: ' + err.message }
    } finally {
      this.isSubmitting.value = false
    }
  }

  /**
   * Update an existing user.
   * Validates that username is not empty.
   */
  async updateUser(userId: string, userData: any) {
    if (!userData.username?.trim()) {
      this.statusMessage.value = { type: 'error', text: 'Username is required.' }
      return
    }

    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      await api.updateUser(userId, userData)
      this.statusMessage.value = { type: 'success', text: 'User updated.' }
      await this.fetchUsers()
    } catch (err: any) {
      console.error('[UserService] Failed to update user:', err)
      this.statusMessage.value = { type: 'error', text: 'Failed to update user: ' + err.message }
    } finally {
      this.isSubmitting.value = false
    }
  }

  /**
   * Delete a user from the system.
   * Requires user confirmation before deletion.
   */
  async deleteUser(userId: string, username: string) {
    if (!confirm(`Are you sure you want to delete user "${username}"?`)) {
      return
    }

    try {
      await api.deleteUser(userId)
      this.statusMessage.value = { type: 'success', text: 'User removed.' }
      await this.fetchUsers()
    } catch (err: any) {
      console.error('[UserService] Failed to delete user:', err)
      this.statusMessage.value = { type: 'error', text: 'Failed to delete user: ' + err.message }
    }
  }
}

export const userService = new UserService()
