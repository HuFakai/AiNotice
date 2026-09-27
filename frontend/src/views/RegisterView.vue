<script setup>
/**
 * 注册 /register
 * - POST /auth/register {username, email, password, display_name?}
 * - 用户名/邮箱可用性：输入停顿 500ms 防抖后调用 /auth/check-username、/auth/check-email
 * - 服务端关闭注册时返回 400/403，detail 原样展示
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { checkEmail, checkUsername } from '../api/auth.js'
import { debounce, errorText, isValidEmail, isValidUsername, passwordStrength } from '../lib/format.js'
import { toastSuccess } from '../lib/toast.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

const form = ref({
  username: '',
  email: '',
  password: '',
  confirm: '',
  display_name: '',
})

const submitting = ref(false)
const errorMessage = ref('')

/** 每个字段的可用性状态：idle | checking | available | taken | invalid */
const usernameState = ref('idle')
const usernameMessage = ref('')
const emailState = ref('idle')
const emailMessage = ref('')

const strength = computed(() => passwordStrength(form.value.password))
const passwordMismatch = computed(() => Boolean(form.value.confirm) && form.value.password !== form.value.confirm)

const canSubmit = computed(
  () =>
    isValidUsername(form.value.username) &&
    isValidEmail(form.value.email) &&
    strength.value.checks.minLength &&
    form.value.password === form.value.confirm &&
    form.value.confirm.length > 0
)

/* ---------------- 可用性检查（500ms 防抖）---------------- */

const runUsernameCheck = debounce(async (value) => {
  if (!isValidUsername(value)) {
    usernameState.value = 'invalid'
    usernameMessage.value = '用户名需 3-50 位，仅限字母、数字、下划线'
    return
  }

  usernameState.value = 'checking'
  usernameMessage.value = '检查中…'
  try {
    const data = await checkUsername(value)
    if (form.value.username.trim() !== value) return // 已被后续输入取代
    usernameState.value = data?.available ? 'available' : 'taken'
    usernameMessage.value = data?.message || (data?.available ? '该用户名可用' : '该用户名已被占用')
  } catch (err) {
    usernameState.value = 'idle'
    usernameMessage.value = err?.status === 429 ? '检查过于频繁，请稍后再试' : ''
  }
}, 500)

const runEmailCheck = debounce(async (value) => {
  if (!isValidEmail(value)) {
    emailState.value = 'invalid'
    emailMessage.value = '请输入有效的邮箱地址'
    return
  }

  emailState.value = 'checking'
  emailMessage.value = '检查中…'
  try {
    const data = await checkEmail(value)
    if (form.value.email.trim() !== value) return
    emailState.value = data?.available ? 'available' : 'taken'
    emailMessage.value = data?.message || (data?.available ? '该邮箱可用' : '该邮箱已被注册')
  } catch (err) {
    emailState.value = 'idle'
    emailMessage.value = err?.status === 429 ? '检查过于频繁，请稍后再试' : ''
  }
}, 500)

watch(
  () => form.value.username,
  (value) => {
    const v = String(value || '').trim()
    if (!v) {
      usernameState.value = 'idle'
      usernameMessage.value = ''
      return
    }
    runUsernameCheck(v)
  }
)

watch(
  () => form.value.email,
  (value) => {
    const v = String(value || '').trim()
    if (!v) {
      emailState.value = 'idle'
      emailMessage.value = ''
      return
    }
    runEmailCheck(v)
  }
)

onBeforeUnmount(() => {
  runUsernameCheck.cancel?.()
  runEmailCheck.cancel?.()
})

/* ---------------- 提交 ---------------- */

async function onSubmit() {
  if (submitting.value) return
  errorMessage.value = ''

  if (!isValidUsername(form.value.username)) {
    errorMessage.value = '用户名需 3-50 位，仅限字母、数字、下划线'
    return
  }
  if (!isValidEmail(form.value.email)) {
    errorMessage.value = '请输入有效的邮箱地址'
    return
  }
  if (!strength.value.checks.minLength) {
    errorMessage.value = '密码至少需要 8 位'
    return
  }
  if (form.value.password !== form.value.confirm) {
    errorMessage.value = '两次输入的密码不一致'
    return
  }
  if (usernameState.value === 'taken') {
    errorMessage.value = '该用户名已被占用，请更换'
    return
  }
  if (emailState.value === 'taken') {
    errorMessage.value = '该邮箱已被注册，请更换'
    return
  }

  submitting.value = true
  try {
    const payload = {
      username: form.value.username.trim(),
      email: form.value.email.trim(),
      password: form.value.password,
    }
    const displayName = form.value.display_name.trim()
    if (displayName) payload.display_name = displayName

    const data = await auth.register(payload)
    toastSuccess(data?.message || '注册成功，请登录')
    await router.replace({ path: '/login' })
  } catch (err) {
    errorMessage.value = errorText(err, '注册失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

const strengthLevelText = computed(() => {
  const level = strength.value.level
  if (level === 'strong') return 'STRONG'
  if (level === 'medium') return 'MEDIUM'
  return 'WEAK'
})
</script>

<template>
  <div class="auth">
    <div class="auth__card auth__card--wide">
      <div class="auth__head">
        <div class="auth__logo">
          <span class="auth__logoDot" aria-hidden="true"><i></i></span>
          <span class="auth__brand">
            <span class="auth__brandName">爱通知 AiNotice</span>
            <span class="auth__brandSub">XIAOAI SPEAK API</span>
          </span>
        </div>
        <h1 class="auth__title">创建账号</h1>
        <p class="auth__sub">注册后即可创建密钥、绑定音箱并推送消息</p>
      </div>

      <div class="auth__body">
        <form novalidate @submit.prevent="onSubmit">
          <div class="field">
            <label class="field__label" for="reg-username">
              用户名<span class="req">*</span>
            </label>
            <input
              id="reg-username"
              v-model="form.username"
              class="input"
              :class="{ 'input--invalid': usernameState === 'taken' || usernameState === 'invalid' }"
              type="text"
              autocomplete="username"
              placeholder="letters_numbers_only"
              :disabled="submitting"
              data-autofocus
            />
            <div v-if="usernameMessage" class="field__state" :class="`field__state--${
              usernameState === 'available' ? 'ok' : usernameState === 'checking' ? 'busy' : 'bad'
            }`">
              <span v-if="usernameState === 'checking'" class="spinner" style="width: 11px; height: 11px"></span>
              <span v-else class="led" :class="usernameState === 'available' ? 'led--success' : 'led--error'"></span>
              <span>{{ usernameMessage }}</span>
            </div>
            <div v-else class="field__hint">3-50 位，仅限字母、数字与下划线</div>
          </div>

          <div class="field">
            <label class="field__label" for="reg-email">
              邮箱<span class="req">*</span>
            </label>
            <input
              id="reg-email"
              v-model="form.email"
              class="input"
              :class="{ 'input--invalid': emailState === 'taken' || emailState === 'invalid' }"
              type="email"
              autocomplete="email"
              placeholder="you@example.com"
              :disabled="submitting"
            />
            <div v-if="emailMessage" class="field__state" :class="`field__state--${
              emailState === 'available' ? 'ok' : emailState === 'checking' ? 'busy' : 'bad'
            }`">
              <span v-if="emailState === 'checking'" class="spinner" style="width: 11px; height: 11px"></span>
              <span v-else class="led" :class="emailState === 'available' ? 'led--success' : 'led--error'"></span>
              <span>{{ emailMessage }}</span>
            </div>
            <div v-else class="field__hint">用于登录与接收通知</div>
          </div>

          <div class="field">
            <label class="field__label" for="reg-password">
              密码<span class="req">*</span>
            </label>
            <input
              id="reg-password"
              v-model="form.password"
              class="input"
              type="password"
              autocomplete="new-password"
              placeholder="至少 8 位"
              :disabled="submitting"
            />
            <div class="pw-meter">
              <div class="pw-meter__bars">
                <i
                  v-for="i in 5"
                  :key="i"
                  class="pw-meter__bar"
                  :class="i <= strength.score ? `pw-meter__bar--on-${strength.level}` : ''"
                ></i>
              </div>
              <span class="pw-meter__text">{{ strengthLevelText }}</span>
            </div>
          </div>

          <div class="field">
            <label class="field__label" for="reg-confirm">
              确认密码<span class="req">*</span>
            </label>
            <input
              id="reg-confirm"
              v-model="form.confirm"
              class="input"
              :class="{ 'input--invalid': passwordMismatch }"
              type="password"
              autocomplete="new-password"
              placeholder="再次输入密码"
              :disabled="submitting"
            />
            <div v-if="passwordMismatch" class="field__error">两次输入的密码不一致</div>
          </div>

          <div class="field">
            <label class="field__label" for="reg-display">显示名称</label>
            <input
              id="reg-display"
              v-model="form.display_name"
              class="input"
              type="text"
              autocomplete="nickname"
              placeholder="可选，控制台展示用"
              :disabled="submitting"
            />
          </div>

          <div v-if="errorMessage" class="notice notice--error mb-3" role="alert">
            <span class="led led--error" aria-hidden="true"></span>
            <span>{{ errorMessage }}</span>
          </div>

          <button type="submit" class="btn btn--primary btn--lg btn--block" :disabled="submitting || !canSubmit">
            <span v-if="submitting" class="spinner"></span>
            <span>{{ submitting ? '正在创建账号' : '注册' }}</span>
          </button>
        </form>
      </div>

      <div class="auth__foot">
        <span>已有账号？</span>
        <RouterLink to="/login">返回登录</RouterLink>
      </div>
    </div>

    <div class="auth__sign">
      <span>AINOTICE</span>
      <span class="auth__signSep">·</span>
      <span>小爱音箱消息推送 API 平台</span>
    </div>
  </div>
</template>
