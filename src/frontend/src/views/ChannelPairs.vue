<script setup lang="ts">
import { message, Modal } from 'ant-design-vue';
import { onMounted, ref } from 'vue';

import { approveChannelPair, listChannelPairs, type ChannelPair } from '@/api/admin';

const pairs = ref<ChannelPair[]>([]);
const loading = ref(false);

const columns = [
  { title: 'Name', dataIndex: 'name', key: 'name' },
  { title: 'TG Chat ID', dataIndex: 'tg_chat_id', key: 'tg_chat_id' },
  { title: 'Status', key: 'status', width: 120 },
  { title: 'Express Chat ID', dataIndex: 'express_chat_id', key: 'express_chat_id' },
  { title: '', key: 'actions', width: 120 },
];

async function load() {
  loading.value = true;
  try {
    pairs.value = await listChannelPairs();
  } catch {
    message.error('Failed to load channel pairs');
  } finally {
    loading.value = false;
  }
}

function confirmApprove(pair: ChannelPair) {
  Modal.confirm({
    title: 'Approve channel pair?',
    content: pair.name || `TG Chat ${pair.tg_chat_id}`,
    async onOk() {
      try {
        await approveChannelPair(pair.id);
        message.success('Approved');
        await load();
      } catch {
        message.error('Approve failed');
      }
    },
  });
}

onMounted(load);
</script>

<template>
  <h2 style="margin-bottom: 16px">Channel Pairs</h2>
  <a-table :columns="columns" :data-source="pairs" :loading="loading" :pagination="false" row-key="id" size="middle">
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'status'">
        <a-tag :color="record.is_approved ? 'green' : 'orange'">
          {{ record.is_approved ? 'Approved' : 'Pending' }}
        </a-tag>
      </template>
      <template v-if="column.key === 'express_chat_id'">
        {{ record.express_chat_id || '—' }}
      </template>
      <template v-if="column.key === 'actions'">
        <a-button v-if="!record.is_approved" type="primary" size="small" @click="confirmApprove(record)">
          Approve
        </a-button>
      </template>
    </template>
  </a-table>
</template>
