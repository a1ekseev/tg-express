<script setup lang="ts">
import { message, Modal } from 'ant-design-vue';
import { onMounted, ref } from 'vue';

import { approveChannelPair, listChannelPairs, type ChannelPair } from '@/api/admin';

const pairs = ref<ChannelPair[]>([]);
const loading = ref(false);
const modalOpen = ref(false);
const modalPairId = ref('');
const modalName = ref('');

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

function openApprove(pair: ChannelPair) {
  modalPairId.value = pair.id;
  modalName.value = pair.name || '';
  modalOpen.value = true;
}

async function doApprove() {
  try {
    await approveChannelPair(modalPairId.value, modalName.value);
    message.success('Approved');
    modalOpen.value = false;
    await load();
  } catch {
    message.error('Approve failed');
  }
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
        <a-button v-if="!record.is_approved" type="primary" size="small" @click="openApprove(record)">
          Approve
        </a-button>
      </template>
    </template>
  </a-table>

  <a-modal v-model:open="modalOpen" title="Approve Channel Pair" @ok="doApprove">
    <a-form layout="vertical">
      <a-form-item label="Express Chat Name">
        <a-input v-model:value="modalName" placeholder="Name for the Express chat" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>
