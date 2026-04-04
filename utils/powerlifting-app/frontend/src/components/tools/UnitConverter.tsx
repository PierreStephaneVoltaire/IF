import { useState, useMemo } from 'react'
import { ArrowLeftRight } from 'lucide-react'
import { kgToLb, lbToKg } from '@/utils/units'

type ConversionMode = 'kg-to-lb' | 'lb-to-kg'

export default function UnitConverter() {
  const [mode, setMode] = useState<ConversionMode>('kg-to-lb')
  const [inputValue, setInputValue] = useState('')

  const result = useMemo(() => {
    const value = parseFloat(inputValue)
    if (isNaN(value) || value <= 0) return null

    if (mode === 'kg-to-lb') {
      return {
        from: `${value} kg`,
        to: `${kgToLb(value)} lb`,
      }
    } else {
      return {
        from: `${value} lb`,
        to: `${lbToKg(value)} kg`,
      }
    }
  }, [inputValue, mode])

  const toggleMode = () => {
    setMode((prev) => (prev === 'kg-to-lb' ? 'lb-to-kg' : 'kg-to-lb'))
    setInputValue('')
  }

  const quickValues = useMemo(() => {
    if (mode === 'kg-to-lb') {
      return [20, 45, 60, 75, 90, 100, 120, 140, 160, 180, 200, 220, 250]
    }
    return [45, 100, 135, 185, 205, 225, 275, 315, 365, 405, 455, 495, 585]
  }, [mode])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold mb-2">kg / lb Converter</h2>
        <p className="text-muted-foreground">
          Convert between kilograms and pounds
        </p>
      </div>

      {/* Mode Toggle */}
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => setMode('kg-to-lb')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              mode === 'kg-to-lb'
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
            }`}
          >
            kg → lb
          </button>
          <button
            onClick={toggleMode}
            className="p-2 rounded-md hover:bg-accent"
          >
            <ArrowLeftRight className="w-5 h-5" />
          </button>
          <button
            onClick={() => setMode('lb-to-kg')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              mode === 'lb-to-kg'
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
            }`}
          >
            lb → kg
          </button>
        </div>
      </div>

      {/* Input */}
      <div className="bg-card border border-border rounded-lg p-6">
        <label className="text-sm text-muted-foreground mb-2 block">
          Enter weight in {mode === 'kg-to-lb' ? 'kilograms' : 'pounds'}
        </label>
        <div className="flex items-center gap-4">
          <input
            type="number"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={mode === 'kg-to-lb' ? 'e.g., 100' : 'e.g., 225'}
            className="flex-1 px-4 py-3 text-2xl font-bold border border-border rounded-lg bg-background text-center"
            step={mode === 'kg-to-lb' ? 0.5 : 1}
          />
          <span className="text-xl font-medium text-muted-foreground">
            {mode === 'kg-to-lb' ? 'kg' : 'lb'}
          </span>
        </div>

        {/* Result */}
        {result && (
          <div className="mt-6 p-4 bg-primary/10 rounded-lg text-center">
            <p className="text-sm text-muted-foreground mb-1">
              {result.from} equals
            </p>
            <p className="text-3xl font-bold text-primary">
              {result.to}
            </p>
          </div>
        )}
      </div>

      {/* Quick Reference */}
      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="font-medium mb-3">Quick Reference</h3>
        <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-7 gap-2">
          {quickValues.map((value) => (
            <button
              key={value}
              onClick={() => setInputValue(String(value))}
              className="px-3 py-2 text-sm bg-secondary rounded-md hover:bg-secondary/80 transition-colors"
            >
              {value} {mode === 'kg-to-lb' ? 'kg' : 'lb'}
            </button>
          ))}
        </div>
      </div>

      {/* Conversion Table */}
      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="font-medium mb-3">Common Conversions</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="font-medium mb-2">kg → lb</p>
            <div className="space-y-1 text-muted-foreground">
              <p>50 kg = 110.2 lb</p>
              <p>75 kg = 165.3 lb</p>
              <p>100 kg = 220.5 lb</p>
              <p>125 kg = 275.6 lb</p>
              <p>150 kg = 330.7 lb</p>
              <p>200 kg = 440.9 lb</p>
              <p>250 kg = 551.2 lb</p>
            </div>
          </div>
          <div>
            <p className="font-medium mb-2">lb → kg</p>
            <div className="space-y-1 text-muted-foreground">
              <p>135 lb = 61.2 kg</p>
              <p>185 lb = 83.9 kg</p>
              <p>225 lb = 102.1 kg</p>
              <p>275 lb = 124.7 kg</p>
              <p>315 lb = 142.9 kg</p>
              <p>405 lb = 183.7 kg</p>
              <p>495 lb = 224.5 kg</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
