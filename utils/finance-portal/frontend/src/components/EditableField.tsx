import { useState, useRef, useEffect, useCallback } from 'react';
import { formatCurrency, formatPercent, parseCurrency } from '../utils/formatters';

type FieldType = 'currency' | 'percent' | 'number' | 'text' | 'date';

interface EditableFieldProps {
  value: number | string;
  type?: FieldType;
  onSave: (value: number | string) => Promise<void> | void;
  formatter?: (value: number | string) => string;
  className?: string;
  displayClassName?: string;
  inputClassName?: string;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  decimals?: number;
  disabled?: boolean;
  showEditIcon?: boolean;
}

export function EditableField({
  value,
  type = 'text',
  onSave,
  formatter,
  className = '',
  displayClassName = '',
  inputClassName = '',
  placeholder = '-',
  min,
  max,
  step,
  decimals = 2,
  disabled = false,
  showEditIcon = true,
}: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const formatValue = useCallback((val: number | string): string => {
    if (val === null || val === undefined || val === '') return placeholder;

    if (formatter) return formatter(val);

    switch (type) {
      case 'currency':
        return formatCurrency(val as number);
      case 'percent':
        return formatPercent(val as number, decimals);
      case 'number':
        return (val as number).toFixed(decimals);
      default:
        return String(val);
    }
  }, [type, formatter, placeholder, decimals]);

  const parseValue = useCallback((val: string): number | string => {
    switch (type) {
      case 'currency':
        return parseCurrency(val);
      case 'percent':
        return parseFloat(val.replace(/[^0-9.-]/g, ''));
      case 'number':
        return parseFloat(val) || 0;
      default:
        return val;
    }
  }, [type]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleClick = () => {
    if (disabled) return;
    setIsEditing(true);
    setEditValue(type === 'text' ? String(value) : String(value ?? ''));
  };

  const handleSave = async () => {
    if (isSaving) return;

    const parsedValue = parseValue(editValue);
    const originalValue = value;

    // Only save if value changed
    if (parsedValue !== originalValue) {
      setIsSaving(true);
      try {
        await onSave(parsedValue);
      } catch (error) {
        console.error('Failed to save:', error);
        // Revert on error
        setEditValue(String(originalValue));
      } finally {
        setIsSaving(false);
      }
    }

    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditValue(String(value));
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  const handleBlur = () => {
    handleSave();
  };

  if (isEditing) {
    return (
      <div className={`inline-flex items-center gap-1 ${className}`}>
        <input
          ref={inputRef}
          type={type === 'currency' || type === 'number' || type === 'percent' ? 'number' : type}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          min={min}
          max={max}
          step={step ?? (type === 'currency' ? 0.01 : type === 'percent' ? 0.1 : undefined)}
          placeholder={placeholder}
          disabled={isSaving}
          className={`
            px-2 py-1 text-sm border border-blue-500 rounded
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
            ${isSaving ? 'bg-gray-100' : 'bg-white'}
            ${inputClassName}
          `}
        />
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="p-1 text-green-600 hover:bg-green-50 rounded"
          title="Save"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </button>
        <button
          onClick={handleCancel}
          disabled={isSaving}
          className="p-1 text-red-600 hover:bg-red-50 rounded"
          title="Cancel"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <span
      onClick={handleClick}
      className={`
        inline-flex items-center gap-1 cursor-pointer
        hover:bg-blue-50 hover:underline rounded px-1
        ${disabled ? 'cursor-default hover:bg-transparent hover:no-underline' : ''}
        ${className}
      `}
      title={disabled ? undefined : 'Click to edit'}
    >
      <span className={displayClassName}>{formatValue(value)}</span>
      {showEditIcon && !disabled && (
        <svg className="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
      )}
    </span>
  );
}

export default EditableField;
