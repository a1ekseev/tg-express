import { createRouter, createWebHistory } from 'vue-router';

import { isAuthenticated } from './api/admin';
import ChannelPairs from './views/ChannelPairs.vue';
import Employees from './views/Employees.vue';
import Login from './views/Login.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'Login', component: Login, meta: { public: true } },
    { path: '/', redirect: '/channel-pairs' },
    { path: '/channel-pairs', name: 'ChannelPairs', component: ChannelPairs },
    { path: '/employees', name: 'Employees', component: Employees },
  ],
});

router.beforeEach((to) => {
  if (!to.meta.public && !isAuthenticated()) {
    return '/login';
  }
});
