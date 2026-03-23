<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import { isAuthenticated, logout } from '@/api/admin';

const route = useRoute();
const selectedKeys = computed(() => [route.path]);
const showLayout = computed(() => route.path !== '/login');
</script>

<template>
  <template v-if="showLayout">
    <a-layout style="min-height: 100vh">
      <a-layout-sider :width="220" theme="light" :breakpoint="'lg'" :collapsed-width="0">
        <div style="padding: 16px; font-weight: bold; font-size: 16px; text-align: center">
          TG-Express Admin
        </div>
        <a-menu mode="inline" :selected-keys="selectedKeys">
          <a-menu-item key="/channel-pairs">
            <router-link to="/channel-pairs">Channel Pairs</router-link>
          </a-menu-item>
          <a-menu-item key="/employees">
            <router-link to="/employees">Employees</router-link>
          </a-menu-item>
        </a-menu>
        <div style="padding: 16px; position: absolute; bottom: 0; width: 100%">
          <a-button block @click="logout">Logout</a-button>
        </div>
      </a-layout-sider>
      <a-layout>
        <a-layout-content style="padding: 24px">
          <router-view />
        </a-layout-content>
      </a-layout>
    </a-layout>
  </template>
  <template v-else>
    <router-view />
  </template>
</template>
