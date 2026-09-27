<script setup>
/**
 * 登录 /login
 * - POST /auth/login {username_or_email, password}
 * - 登录限流文案（如「登录尝试过于频繁，请 N 分钟后再试」）原样展示
 * - 成功后跳转 redirect（仅站内路径，客户端与服务端双重校验）
 * - 已登录访问本页由路由守卫直接跳回首页
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { isSafeInternalPath } from '../api/client.js'
import { errorText } from '../lib/format.js'
import { toastSuccess } from '../lib/toast.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = ref({ username_or_email: '', password: '' })
const submitting = ref(false)
const errorMessage = ref('')

const redirectTarget = computed(() => {
  const raw = route.query.redirect
  return typeof raw === 'string' && isSafeInternalPath(raw) && !raw.startsWith('/login') ? raw : '/'
})

const canSubmit = computed(() => form.value.username_or_email.trim() && form.value.password)

async function onSubmit() {
  if (submitting.value) return
  errorMessage.value = ''

  if (!form.value.username_or_email.trim() || !form.value.password) {
    errorMessage.value = '请输入账号与密码'
    return
  }

  submitting.value = true
  try {
    await auth.login({
      username_or_email: form.value.username_or_email.trim(),
      password: form.value.password,
    })
    toastSuccess('登录成功，正在进入控制台')
    await router.replace(redirectTarget.value)
  } catch (err) {
    // 后端的限流/锁定文案原样展示，不二次包装
    errorMessage.value = errorText(err, '登录失败，请检查账号与密码')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth">
    <div class="auth__card">
      <div class="auth__head">
        <div class="auth__logo">
          <span class="auth__logoDot" aria-hidden="true"><i></i></span>
          <span class="auth__brand">
            <span class="auth__brandName">爱通知 AiNotice</span>
            <span class="auth__brandSub">XIAOAI SPEAK API</span>
          </span>
        </div>
        <h1 class="auth__title">登录控制台</h1>
        <p class="auth__sub">使用账号登录，管理密钥、设备与播报任务</p>
      </div>

      <div class="auth__body">
        <form novalidate @submit.prevent="onSubmit">
          <div class="field">
            <label class="field__label" for="login-account">用户名 / 邮箱</label>
            <input
              id="login-account"
              v-model="form.username_or_email"
              class="input"
              type="text"
              autocomplete="username"
              placeholder="demo@xiaoai-api.com"
              :disabled="submitting"
              data-autofocus
            />
          </div>

          <div class="field">
            <label class="field__label" for="login-password">密码</label>
            <input
              id="login-password"
              v-model="form.password"
              class="input"
              type="password"
              autocomplete="current-password"
              placeholder="请输入登录密码"
              :disabled="submitting"
            />
          </div>

          <div v-if="errorMessage" class="notice notice--error mb-3" role="alert">
            <span class="led led--error" aria-hidden="true"></span>
            <span>{{ errorMessage }}</span>
          </div>

          <button type="submit" class="btn btn--primary btn--lg btn--block" :disabled="submitting || !canSubmit">
            <span v-if="submitting" class="spinner"></span>
            <span>{{ submitting ? '正在校验凭据' : '登录' }}</span>
          </button>
        </form>
      </div>

      <div class="auth__foot">
        <span>还没有账号？</span>
        <RouterLink to="/register">立即注册</RouterLink>
      </div>
    </div>

    <div class="auth__sign">
      <span>AINOTICE</span>
      <span class="auth__signSep">·</span>
      <span>小爱音箱消息推送 API 平台</span>
    </div>
  </div>
</template>
