'use client';

import { RiSearchLine } from '@remixicon/react';
import { useState } from 'react';
import { ListBox, ListBoxItem } from 'react-aria-components';
import { CheckboxGlyph } from '@/components/base/checkbox/checkbox-glyph';
import { Input } from '@/components/base/input/input';
import { matches } from '@/lib/format';
import type { EnvironmentSummary } from '@/lib/types';
import { cx } from '@/utils/cx';

interface EnvPickerProps {
  envs: EnvironmentSummary[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}

/** Searchable multi-select of environments (Space toggles, arrow keys move). */
export function EnvPicker({ envs, selected, onChange }: EnvPickerProps) {
  const [query, setQuery] = useState('');
  const shown = envs.filter((env) => matches(query, env.name, env.id, env.family, env.domain));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-body-medium text-text-primary">Environments</span>
        <span className="flex items-center gap-2 text-caption-1-medium text-text-tertiary">
          {selected.size} selected
          {selected.size > 0 && (
            <button
              type="button"
              onClick={() => onChange(new Set())}
              className="cursor-pointer text-accent-400 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-border-focus-ring"
            >
              Clear
            </button>
          )}
        </span>
      </div>
      <Input
        size="small"
        leadingIcon={RiSearchLine}
        placeholder="Filter environments"
        aria-label="Filter environments"
        value={query}
        onChange={setQuery}
      />
      <ListBox
        aria-label="Environments"
        selectionMode="multiple"
        items={shown}
        selectedKeys={selected}
        onSelectionChange={(keys) =>
          onChange(new Set(keys === 'all' ? shown.map((env) => env.id) : [...keys].map(String)))
        }
        renderEmptyState={() => (
          <p className="p-3 text-body-2-regular text-text-tertiary">No single-turn match</p>
        )}
        className="scrollbar-thin flex max-h-52 flex-col gap-0.5 overflow-y-auto rounded-2lg border border-border-button-default bg-background-primary-default p-1 outline-none"
      >
        {(env) => (
          <ListBoxItem
            id={env.id}
            textValue={env.name}
            className={({ isFocused }) =>
              cx(
                'flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 outline-none',
                isFocused && 'bg-dropdown-item-hover-background',
              )
            }
          >
            {({ isSelected, isFocusVisible, isHovered, isDisabled }) => (
              <>
                <CheckboxGlyph
                  size="sm"
                  state={{ isSelected, isIndeterminate: false, isFocusVisible, isHovered, isDisabled }}
                />
                <span className="min-w-0 flex-1 truncate text-body-2-medium text-text-primary">
                  {env.name}
                </span>
                <span className="truncate font-mono text-caption-2-medium text-text-tertiary">{env.id}</span>
              </>
            )}
          </ListBoxItem>
        )}
      </ListBox>
    </div>
  );
}
