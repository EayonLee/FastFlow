<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getWorkflows, createWorkflow, updateWorkflow, deleteWorkflow, type WorkflowResponse } from '@/services/workflowService'
import GlobalHeader from '@/components/common/GlobalHeader.vue'
import GlobalFooter from '@/components/common/GlobalFooter.vue'

const router = useRouter()
const { t } = useI18n()

const workflows = ref<WorkflowResponse[]>([])
const isModalOpen = ref(false)
const isEditMode = ref(false)
const editingId = ref<string | null>(null)
const newWorkflow = ref({
  name: '',
  description: ''
})

const errors = ref({
  name: '',
  description: ''
})

const activeDropdown = ref<string | null>(null)
const isDeleteModalOpen = ref(false)
const workflowToDelete = ref<WorkflowResponse | null>(null)
const deleteConfirmationName = ref('')

const loadWorkflows = async () => {
  try {
    const data = await getWorkflows()
    workflows.value = data || []
  } catch (e) {
    console.error('Failed to load workflows', e)
    workflows.value = []
  }
}

const openWorkflow = (id: string) => {
  router.push(`/workflow/${id}`)
}

const openCreateModal = () => {
  isEditMode.value = false
  editingId.value = null
  newWorkflow.value = { name: '', description: '' }
  errors.value = { name: '', description: '' }
  isModalOpen.value = true
}

const closeModal = () => {
  isModalOpen.value = false
  isEditMode.value = false
  editingId.value = null
}

const handleEdit = (wf: WorkflowResponse) => {
  closeDropdown()
  isEditMode.value = true
  editingId.value = wf.id
  newWorkflow.value = {
    name: wf.name,
    description: wf.description
  }
  errors.value = { name: '', description: '' }
  isModalOpen.value = true
}

const confirmCreate = async () => {
  // Reset errors
  errors.value = { name: '', description: '' }
  let isValid = true

  if (!newWorkflow.value.name.trim()) {
    errors.value.name = t('workflows.name_required')
    isValid = false
  } else if (newWorkflow.value.name.length > 30) {
    errors.value.name = t('workflows.name_too_long')
    isValid = false
  }
  
  if (!newWorkflow.value.description.trim()) {
    errors.value.description = t('workflows.desc_required')
    isValid = false
  } else if (newWorkflow.value.description.length > 50) {
    errors.value.description = t('workflows.desc_too_long')
    isValid = false
  }

  if (!isValid) return

  try {
    if (isEditMode.value && editingId.value) {
      // Update existing
      await updateWorkflow(editingId.value, {
        name: newWorkflow.value.name,
        description: newWorkflow.value.description
      })
      await loadWorkflows()
      closeModal()
    } else {
      // Create new
      await createWorkflow({
        name: newWorkflow.value.name,
        description: newWorkflow.value.description
      })
      
      await loadWorkflows()
      closeModal()
    }
  } catch (e) {
    console.error('Failed to save workflow', e)
  }
}

const toggleDropdown = (e: Event, id: string) => {
  e.stopPropagation()
  if (activeDropdown.value === id) {
    activeDropdown.value = null
  } else {
    activeDropdown.value = id
  }
}

const closeDropdown = () => {
  activeDropdown.value = null
}

const handleDelete = (wf: WorkflowResponse) => {
  closeDropdown()
  workflowToDelete.value = wf
  deleteConfirmationName.value = ''
  isDeleteModalOpen.value = true
}

const closeDeleteModal = () => {
  isDeleteModalOpen.value = false
  workflowToDelete.value = null
  deleteConfirmationName.value = ''
}

const confirmDelete = async () => {
  if (!workflowToDelete.value) return
  
  if (deleteConfirmationName.value !== workflowToDelete.value.name) {
    alert(t('common.confirm_error') || 'Name does not match') // Fallback or add to locale if strict
    return
  }

  try {
    if (workflowToDelete.value.id) {
      await deleteWorkflow(workflowToDelete.value.id)
      await loadWorkflows()
    }
  } catch (e) {
    console.error('Failed to delete workflow', e)
  }
  
  closeDeleteModal()
}

// Click outside to close dropdowns
const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.wf-actions-btn') && !target.closest('.wf-dropdown')) {
    activeDropdown.value = null
  }
}

onMounted(() => {
  loadWorkflows()
  document.addEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="workflow-list-view">
    <GlobalHeader />
    
    <div class="scroll-container">
      <div class="content-wrapper">
        <div class="page-header">
        <h1>{{ t('workflows.title') }}</h1>
        <button class="btn-neon" @click="openCreateModal">+ {{ t('workflows.new') }}</button>
      </div>
      
      <div class="wf-grid">
        <div 
          v-for="wf in workflows" 
          :key="wf.id" 
          class="wf-card"
          @click="openWorkflow(wf.id)"
        >
          <div class="wf-card-header">
            <div class="wf-icon-box">
              <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
              </svg>
            </div>
            <h3>{{ wf.name }}</h3>
          </div>
          
          <!-- Actions Menu -->
          <div class="wf-actions-wrapper">
            <button class="wf-actions-btn" @click="(e) => toggleDropdown(e, wf.id)">
              •••
            </button>
            <div v-if="activeDropdown === wf.id" class="wf-dropdown">
              <div class="wf-dropdown-item" @click.stop="handleEdit(wf)">
                {{ t('common.edit') }}
              </div>
              <div class="wf-dropdown-item danger" @click.stop="handleDelete(wf)">
                {{ t('common.delete') }}
              </div>
            </div>
          </div>
          <div class="wf-card-body">
            <p class="wf-desc">{{ wf.description }}</p>
          </div>
          <div class="wf-card-footer">
            <div class="wf-author" :title="wf.creatorName">
              <div class="wf-avatar">
                {{ (wf.creatorName || 'U').charAt(0).toUpperCase() }}
              </div>
              <span class="wf-author-name">{{ wf.creatorName || 'Unknown' }}</span>
            </div>
            <div class="wf-footer-right">
              <span class="wf-time">{{ wf.updatedAt }}</span>
            </div>
          </div>
        </div>
        
        <!-- Empty State Visual if needed -->
        <div v-if="workflows.length === 0" class="empty-state">
            <p>{{ t('workflows.empty_desc') }}</p>
          </div>
        </div>
      </div>
      <GlobalFooter />
    </div>
  </div>

    <!-- Create/Edit Workflow Modal -->
    <div v-if="isModalOpen" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <h2>{{ isEditMode ? t('workflows.edit_title') : t('workflows.create_new') }}</h2>
        
        <div class="form-group">
          <label for="wf-name">
            <span class="required-mark">*</span>
            {{ t('workflows.name_label') }}
          </label>
          <input 
            id="wf-name" 
            v-model="newWorkflow.name" 
            type="text" 
            :class="{ 'input-error': errors.name }"
            :placeholder="t('workflows.name_placeholder')"
            autofocus
            maxlength="30"
            @input="errors.name = ''"
            @keyup.enter="confirmCreate"
          />
          <span v-if="errors.name" class="error-message">{{ errors.name }}</span>
        </div>
        
        <div class="form-group">
          <label for="wf-desc">
            <span class="required-mark">*</span>
            {{ t('workflows.desc_label') }}
          </label>
          <textarea 
            id="wf-desc" 
            v-model="newWorkflow.description" 
            :class="{ 'input-error': errors.description }"
            :placeholder="t('workflows.desc_placeholder')"
            maxlength="50"
            @input="errors.description = ''"
          ></textarea>
          <span v-if="errors.description" class="error-message">{{ errors.description }}</span>
        </div>
        
        <div class="modal-actions">
          <button class="btn-ghost" @click="closeModal">{{ t('common.cancel') }}</button>
          <button class="btn-neon" @click="confirmCreate">
            {{ isEditMode ? t('common.save') : t('common.create') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="isDeleteModalOpen" class="modal-overlay" @click.self="closeDeleteModal">
      <div class="modal-content">
        <h2>{{ t('workflows.delete_title') }}</h2>
        
        <div class="form-group">
          <p class="warning-text">
            {{ t('workflows.delete_confirm', { name: workflowToDelete?.name }) }}
          </p>
          <input 
            v-model="deleteConfirmationName" 
            type="text" 
            :placeholder="t('workflows.delete_placeholder')"
            autofocus
          />
        </div>
        
        <div class="modal-actions">
          <button class="btn-ghost" @click="closeDeleteModal">{{ t('common.cancel') }}</button>
          <button 
            class="btn-danger" 
            :disabled="deleteConfirmationName !== workflowToDelete?.name"
            @click="confirmDelete"
          >
            {{ t('common.delete') }}
          </button>
        </div>
      </div>
    </div>
</template>

<style scoped>
.workflow-list-view {
  height: 100vh;
  background-color: var(--bg-app);
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}



.scroll-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  
  /* Scrollbar Styling */
  scrollbar-width: thin;
  scrollbar-color: var(--accent-neon) transparent;
}

.scroll-container::-webkit-scrollbar {
  width: 6px;
}

.scroll-container::-webkit-scrollbar-track {
  background: transparent;
}

.scroll-container::-webkit-scrollbar-thumb {
  background-color: var(--accent-neon);
  border-radius: 3px;
  border: 1px solid var(--bg-app);
}

.scroll-container::-webkit-scrollbar-thumb:hover {
  background-color: #00cc33;
}

.content-wrapper {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px;
  width: 100%;
  box-sizing: border-box;
  flex: 1;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 40px;
}

.page-header h1 {
  margin: 0;
  font-size: 2rem;
  background: linear-gradient(90deg, #fff, #aaa);
  -webkit-background-clip: text;
  background-clip: text;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(5px);
}

.modal-content {
  background: var(--bg-panel);
  padding: 30px;
  border-radius: 12px;
  width: 500px;
  border: 1px solid var(--border-color);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
}

.modal-content h2 {
  margin-top: 0;
  margin-bottom: 24px;
  color: var(--text-primary);
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 1rem;
  box-sizing: border-box;
}

.form-group textarea {
  min-height: 100px;
  resize: vertical;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--accent-neon);
}

.input-error,
.input-error:focus {
  border-color: var(--danger) !important;
  box-shadow: 0 0 5px rgba(255, 51, 51, 0.3);
}

.error-message {
  display: block;
  color: var(--danger);
  font-size: 0.8rem;
  margin-top: 6px;
  font-family: var(--font-mono);
}

.required-mark {
  color: var(--danger);
  margin-right: 4px;
  font-weight: bold;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 30px;
}

.wf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

.wf-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  display: flex;
  flex-direction: column;
  height: 240px;
  position: relative;
  overflow: hidden;
}

.wf-card:hover {
  border-color: var(--accent-neon);
  transform: translateY(-4px);
  box-shadow: 0 10px 30px rgba(0, 255, 65, 0.1);
}

.wf-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 4px;
  background: var(--accent-neon);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.3s ease;
}

.wf-card:hover::before {
  transform: scaleX(1);
}

.wf-card-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.wf-card-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  flex: 1;
  word-break: break-word; /* Allow wrapping */
  line-height: 1.4;
  padding-right: 24px; /* Reserve space for action button */
}

.wf-icon-box {
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-neon);
  transition: all 0.3s;
  flex-shrink: 0; /* Prevent icon shrinking */
}

.wf-card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.wf-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3; /* Limit to 3 lines */
  line-clamp: 3; /* 标准属性，兼容性 */
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Card Footer & Meta Info */
.wf-card-footer {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.wf-author {
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 0.8;
  transition: opacity 0.2s ease;
}

.wf-card:hover .wf-author {
  opacity: 1;
}

.wf-avatar {
  width: 24px;
  height: 24px;
  background: var(--accent-neon);
  color: #000;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 12px;
  font-family: var(--font-mono);
}

.wf-author-name {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-secondary);
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wf-footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wf-time {
  font-size: 0.75rem;
  color: var(--text-dim);
  font-family: 'JetBrains Mono', monospace;
}

/* Actions Menu Styles */
.wf-actions-wrapper {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 5;
}

.wf-actions-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 20px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  line-height: 1;
  transition: color 0.2s;
}

.wf-actions-btn:hover,
.wf-card:hover .wf-actions-btn:hover {
  color: var(--accent-neon);
}

.wf-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  box-shadow: 0 5px 20px rgba(0,0,0,0.5);
  min-width: 120px;
  z-index: 10;
  overflow: hidden;
  margin-top: 4px;
}

.wf-dropdown-item {
  padding: 10px 16px;
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.2s;
}

.wf-dropdown-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.wf-dropdown-item.danger {
  color: var(--danger);
}

.wf-dropdown-item.danger:hover {
  background: rgba(255, 51, 51, 0.1);
}

.warning-text {
  color: var(--text-secondary);
  margin-bottom: 12px;
  font-size: 14px;
}

.btn-danger {
  background: rgba(255, 51, 51, 0.1);
  border: 1px solid var(--danger);
  color: var(--danger);
  padding: 8px 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.btn-danger:hover:not(:disabled) {
  background: var(--danger);
  color: white;
  box-shadow: 0 0 10px rgba(255, 51, 51, 0.4);
}

.btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: var(--border-subtle);
  color: var(--text-dim);
  background: transparent;
}

.arrow {
  transition: transform 0.2s;
}
</style>
