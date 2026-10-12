'use client';

import { Select, SelectItem } from '@/components/base/select/select';

const ALL = '__all__';

interface FilterSelectProps {
  label: string;
  value: string | null;
  options: string[];
  onChange: (value: string | null) => void;
}

/** Compact dropdown filter whose first option clears it ("All ..."). */
export function FilterSelect({ label, value, options, onChange }: FilterSelectProps) {
  return (
    <Select
      aria-label={label}
      size="sm"
      selectedKey={value ?? ALL}
      onSelectionChange={(key) => onChange(key === ALL ? null : String(key))}
      triggerClassName="min-w-36"
    >
      <SelectItem id={ALL}>{`All ${label}`}</SelectItem>
      {options.map((option) => (
        <SelectItem key={option} id={option}>
          {option}
        </SelectItem>
      ))}
    </Select>
  );
}
