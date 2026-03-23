<script setup lang="ts">
import { message } from 'ant-design-vue';
import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { login } from '@/api/admin';

const router = useRouter();
const username = ref('');
const password = ref('');
const loading = ref(false);

async function handleLogin() {
  loading.value = true;
  try {
    await login(username.value, password.value);
    router.push('/channel-pairs');
  } catch {
    message.error('Invalid credentials');
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div style="display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f0f2f5">
    <a-card title="TG-Express Admin" style="width: 360px">
      <a-form layout="vertical" @submit.prevent="handleLogin">
        <a-form-item label="Username">
          <a-input v-model:value="username" placeholder="admin" />
        </a-form-item>
        <a-form-item label="Password">
          <a-input-password v-model:value="password" placeholder="Password" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="loading" block>
            Log in
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>
