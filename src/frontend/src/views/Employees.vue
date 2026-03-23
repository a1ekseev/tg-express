<script setup lang="ts">
import { message, Modal } from 'ant-design-vue';
import { onMounted, ref } from 'vue';

import { deleteEmployee, listEmployees, updateEmployee, type Employee } from '@/api/admin';

const employees = ref<Employee[]>([]);
const loading = ref(false);
const editOpen = ref(false);
const editId = ref('');
const editFullName = ref('');
const editPosition = ref('');

const columns = [
  { title: 'TG User ID', dataIndex: 'tg_user_id', key: 'tg_user_id', width: 140 },
  { title: 'Express HUID', dataIndex: 'express_huid', key: 'express_huid' },
  { title: 'Full Name', dataIndex: 'full_name', key: 'full_name' },
  { title: 'Position', dataIndex: 'position', key: 'position' },
  { title: '', key: 'actions', width: 180 },
];

async function load() {
  loading.value = true;
  try {
    employees.value = await listEmployees();
  } catch {
    message.error('Failed to load employees');
  } finally {
    loading.value = false;
  }
}

function openEdit(emp: Employee) {
  editId.value = emp.id;
  editFullName.value = emp.full_name || '';
  editPosition.value = emp.position || '';
  editOpen.value = true;
}

async function doSave() {
  try {
    await updateEmployee(editId.value, {
      full_name: editFullName.value || null,
      position: editPosition.value || null,
    });
    message.success('Updated');
    editOpen.value = false;
    await load();
  } catch {
    message.error('Update failed');
  }
}

function confirmDelete(emp: Employee) {
  Modal.confirm({
    title: 'Delete employee?',
    content: emp.full_name || `User ${emp.tg_user_id || emp.express_huid}`,
    async onOk() {
      try {
        await deleteEmployee(emp.id);
        message.success('Deleted');
        await load();
      } catch {
        message.error('Delete failed');
      }
    },
  });
}

onMounted(load);
</script>

<template>
  <h2 style="margin-bottom: 16px">Employees</h2>
  <a-table :columns="columns" :data-source="employees" :loading="loading" :pagination="false" row-key="id" size="middle">
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'tg_user_id'">
        {{ record.tg_user_id ?? '—' }}
      </template>
      <template v-if="column.key === 'express_huid'">
        {{ record.express_huid || '—' }}
      </template>
      <template v-if="column.key === 'full_name'">
        {{ record.full_name || '—' }}
      </template>
      <template v-if="column.key === 'position'">
        {{ record.position || '—' }}
      </template>
      <template v-if="column.key === 'actions'">
        <a-space>
          <a-button size="small" @click="openEdit(record)">Edit</a-button>
          <a-button size="small" danger @click="confirmDelete(record)">Delete</a-button>
        </a-space>
      </template>
    </template>
  </a-table>

  <a-modal v-model:open="editOpen" title="Edit Employee" @ok="doSave">
    <a-form layout="vertical">
      <a-form-item label="Full Name">
        <a-input v-model:value="editFullName" placeholder="Full name" />
      </a-form-item>
      <a-form-item label="Position">
        <a-input v-model:value="editPosition" placeholder="Position" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>
