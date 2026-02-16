<script setup>
/**
 * FlowSelect 组件
 * 作用：通用的下拉选择组件，支持自定义图标和颜色。
 * 实现：使用全局点击事件监听实现点击外部关闭，兼容 Shadow DOM 环境。
 * 注意：父容器需要没有 overflow: hidden，否则菜单会被遮挡。
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

const props = defineProps({
  modelValue: {
    type: [String, Number],
    required: true
  },
  options: {
    type: Array,
    required: true,
    // 格式: [{ id, label, icon?, color? }]
  },
  placeholder: {
    type: String,
    default: '请选择'
  },
  position: {
    type: String,
    default: 'top', // 'top' | 'bottom'
    validator: (value) => ['top', 'bottom'].includes(value)
  },
  width: {
    type: String,
    default: 'auto' // 改为 auto 配合 min-width 使用
  },
  minWidth: {
    type: String,
    default: '140px'
  }
})

const emit = defineEmits(['update:modelValue'])

// 组件容器引用
const containerRef = ref(null)

// 控制下拉菜单的显示/隐藏状态
const isOpen = ref(false)

// 计算当前选中的选项对象
const currentOption = computed(() => {
  // 从选项列表中查找 id 匹配的项
  return props.options.find(opt => opt.id === props.modelValue)
})

/**
 * 切换下拉菜单的显示状态
 * 点击触发器时调用
 */
const toggleDropdown = () => {
  // 切换开关状态
  isOpen.value = !isOpen.value
}

/**
 * 关闭下拉菜单
 */
const closeDropdown = () => {
  isOpen.value = false
}

/**
 * 全局点击事件处理
 * 用于检测点击是否在组件外部
 */
const handleGlobalClick = (event) => {
  // 如果菜单未打开，不处理
  if (!isOpen.value) return

  // 使用 composedPath() 获取完整的事件冒泡路径，兼容 Shadow DOM
  const path = event.composedPath()
  
  // 如果点击路径中不包含当前组件容器，说明是点击了外部 -> 关闭菜单
  if (containerRef.value && !path.includes(containerRef.value)) {
    closeDropdown()
  }
}

// 监听 isOpen 状态，动态添加/移除全局点击监听
watch(isOpen, (val) => {
  if (val) {
    // 延迟一帧添加监听，避免当前的打开点击事件立即触发关闭
    setTimeout(() => {
      window.addEventListener('click', handleGlobalClick)
    }, 0)
  } else {
    window.removeEventListener('click', handleGlobalClick)
  }
})

// 组件卸载时清理监听
onUnmounted(() => {
  window.removeEventListener('click', handleGlobalClick)
})

/**
 * 选择某个选项
 * @param {Object} option - 选中的选项对象
 */
const selectOption = (option) => {
  // 触发 update:modelValue 事件更新父组件数据
  emit('update:modelValue', option.id)
  // 选择后关闭菜单
  closeDropdown()
}
</script>

<template>
  <div 
    ref="containerRef"
    class="flow-select-container" 
    :class="{ 'is-open': isOpen }"
    :style="{ width: width, minWidth: minWidth }"
  >
    <!-- 移除之前的全屏遮罩层，改用全局事件监听 -->
    
    <!-- Trigger 触发器部分 -->
    <div 
      class="select-trigger" 
      :class="{ active: isOpen }"
      @click="toggleDropdown"
    >
      <div class="trigger-content">
        <!-- 如果有图标则显示 -->
        <span class="select-icon" v-if="currentOption?.icon">
          <component :is="currentOption.icon" size="14" :color="currentOption.color" />
        </span>
        <!-- 显示当前选中项的标签或占位符 -->
        <span class="select-label">{{ currentOption ? currentOption.label : placeholder }}</span>
      </div>
      <!-- 下拉箭头，根据状态旋转 -->
      <ChevronDown size="12" class="chevron" :class="{ rotated: isOpen }" />
    </div>

    <!-- Dropdown 下拉菜单部分 -->
    <transition name="fade-slide">
      <div 
        v-if="isOpen" 
        class="select-dropdown"
        :class="position"
      >
        <!-- 选项列表 -->
        <div 
          v-for="option in options" 
          :key="option.id"
          class="select-item"
          :class="{ active: modelValue === option.id }"
          @click.stop="selectOption(option)"
        >
          <!-- 选项图标 -->
          <span class="item-icon" v-if="option.icon">
            <component :is="option.icon" size="14" :color="option.color" />
          </span>
          <!-- 选项标签 -->
          <span class="item-label">{{ option.label }}</span>
        </div>
      </div>
    </transition>
  </div>
</template>
