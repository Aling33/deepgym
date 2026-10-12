'use client';

import { RiBox3Line, RiDeleteBinLine, RiFileCopyLine, RiMore2Line } from '@remixicon/react';
import type { ColumnDef } from '@tanstack/react-table';
import { useState } from 'react';
import { Chip } from '@/components/base/badges/chip';
import {
  Dropdown,
  DropdownItem,
  DropdownPopover,
  DropdownTrigger,
} from '@/components/base/dropdown/dropdown';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { timeAgo } from '@/lib/format';
import type { RunningSandbox } from '@/lib/types';

function RowActions({ sandbox, onKill }: { sandbox: RunningSandbox; onKill: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <Dropdown isOpen={open} onOpenChange={setOpen}>
      <DropdownTrigger
        aria-label={`Actions for ${sandbox.id}`}
        className="flex size-7 items-center justify-center rounded-lg text-foreground-icon-secondary hover:bg-background-secondary-hover"
      >
        <RiMore2Line aria-hidden className="size-4" />
      </DropdownTrigger>
      <DropdownPopover aria-label="Sandbox actions" placement="bottom end" className="w-48">
        <DropdownItem
          className="px-2 py-1.5 text-body-2-medium"
          onSelect={() => {
            void navigator.clipboard.writeText(sandbox.id);
            setOpen(false);
          }}
        >
          <RiFileCopyLine aria-hidden className="size-4 text-foreground-icon-secondary" /> Copy name
        </DropdownItem>
        <DropdownItem
          className="px-2 py-1.5 text-body-2-medium text-text-error-primary"
          onSelect={() => {
            setOpen(false);
            onKill();
          }}
        >
          <RiDeleteBinLine aria-hidden className="size-4" /> Kill
        </DropdownItem>
      </DropdownPopover>
    </Dropdown>
  );
}

/** Live containers of one provider. */
export function SandboxTable({
  sandboxes,
  onKill,
}: {
  sandboxes: RunningSandbox[];
  onKill: (sandbox: RunningSandbox) => void;
}) {
  const columns: ColumnDef<RunningSandbox>[] = [
    { id: 'id', accessorKey: 'id', header: 'Name', meta: { className: 'font-mono text-text-primary' } },
    {
      id: 'image',
      accessorKey: 'image',
      header: 'Image',
      meta: { className: 'font-mono text-text-secondary' },
    },
    {
      id: 'state',
      accessorKey: 'state',
      header: 'State',
      cell: ({ row }) => (
        <Chip variant="caption" color={row.original.state === 'running' ? 'lime' : 'neutral'}>
          {row.original.state}
        </Chip>
      ),
    },
    {
      id: 'started',
      accessorKey: 'started',
      header: 'Started',
      cell: ({ row }) => {
        const started = new Date(row.original.started);
        return Number.isNaN(started.getTime()) ? row.original.started : timeAgo(started.toISOString());
      },
      meta: { className: 'whitespace-nowrap text-text-secondary' },
    },
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      cell: ({ row }) => <RowActions sandbox={row.original} onKill={() => onKill(row.original)} />,
      meta: { align: 'end', className: 'w-10' },
    },
  ];
  return (
    <DataTable
      label="Sandboxes"
      data={sandboxes}
      columns={columns}
      empty={<EmptyState icon={RiBox3Line} title="No DeepGym sandboxes running" />}
    />
  );
}
