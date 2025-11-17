import { useState } from 'react'
import { useToast } from '../context/ToastContext'
import { DollarSign, Coins, Crown, Phone, Globe, Scale, Smartphone, Tablet, Gamepad2, PhoneCall, MessageSquare, Play, Users, Plane, Radio, Gift } from 'lucide-react'
import api from '../services/api'

const QuestionnaireModal = ({ isOpen, onClose, onComplete }) => {
  const toast = useToast()
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    budget_range: '',
    usage_type: '',
    data_needs: '',
    preferred_features: []
  })

  const budgetOptions = [
    { value: 'low', label: 'Budget (<Rp 50.000/bulan)', icon: DollarSign, description: 'Paket hemat untuk kebutuhan dasar' },
    { value: 'medium', label: 'Medium (Rp 50.000-150.000/bulan)', icon: Coins, description: 'Paket standar dengan fitur lengkap' },
    { value: 'high', label: 'Premium (>Rp 150.000/bulan)', icon: Crown, description: 'Paket unlimited dengan benefit maksimal' }
  ]

  const usageOptions = [
    { value: 'calls', label: 'Telepon & SMS', icon: Phone, description: 'Lebih sering nelpon dan kirim SMS' },
    { value: 'internet', label: 'Internet', icon: Globe, description: 'Lebih banyak browsing dan streaming' },
    { value: 'both', label: 'Keduanya Seimbang', icon: Scale, description: 'Pakai telepon dan internet sama banyak' }
  ]

  const dataOptions = [
    { value: 'light', label: 'Ringan (<5GB/bulan)', icon: Smartphone, description: 'Chat, email, social media ringan' },
    { value: 'moderate', label: 'Sedang (5-15GB/bulan)', icon: Tablet, description: 'Browsing, streaming music, video call' },
    { value: 'heavy', label: 'Berat (>15GB/bulan)', icon: Gamepad2, description: 'Gaming, streaming HD, download banyak' }
  ]

  const featureOptions = [
    { value: 'unlimited_calls', label: 'Unlimited Calls', icon: PhoneCall },
    { value: 'unlimited_sms', label: 'Unlimited SMS', icon: MessageSquare },
    { value: 'free_whatsapp', label: 'Free WhatsApp', icon: MessageSquare },
    { value: 'free_youtube', label: 'Free YouTube', icon: Play },
    { value: 'free_social_media', label: 'Free Social Media', icon: Users },
    { value: 'international_roaming', label: 'International Roaming', icon: Plane },
    { value: 'hotspot', label: 'Hotspot/Tethering', icon: Radio },
    { value: 'cashback', label: 'Cashback & Rewards', icon: Gift }
  ]

  const handleSelectOption = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleToggleFeature = (feature) => {
    setFormData(prev => ({
      ...prev,
      preferred_features: prev.preferred_features.includes(feature)
        ? prev.preferred_features.filter(f => f !== feature)
        : [...prev.preferred_features, feature]
    }))
  }

  const handleNext = () => {
    if (step < 4) {
      setStep(step + 1)
    }
  }

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1)
    }
  }

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await api.post('/api/v1/users/preferences', formData)
      onComplete?.()
      onClose()
      toast.success('Preferensi berhasil disimpan!')
    } catch (error) {
      console.error('Failed to save preferences:', error)
      toast.error('Gagal menyimpan preferensi. Silakan coba lagi.')
    } finally {
      setLoading(false)
    }
  }

  const canProceed = () => {
    if (step === 1) return formData.budget_range !== ''
    if (step === 2) return formData.usage_type !== ''
    if (step === 3) return formData.data_needs !== ''
    return true
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white p-6 rounded-t-2xl">
          <h2 className="text-2xl font-bold mb-2">✨ Personalisasi Rekomendasi Anda</h2>
          <p className="text-indigo-100">Bantu kami memberikan rekomendasi paket terbaik untuk Anda</p>

          {/* Progress bar */}
          <div className="mt-4 flex gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={`flex-1 h-2 rounded-full transition-all ${
                  i <= step ? 'bg-white' : 'bg-indigo-400'
                }`}
              />
            ))}
          </div>
          <p className="text-sm text-indigo-100 mt-2">Step {step} dari 4</p>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Step 1: Budget Range */}
          {step === 1 && (
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                <DollarSign className="w-6 h-6 text-green-600" />
                Berapa budget Anda untuk paket bulanan?
              </h3>
              <div className="space-y-3">
                {budgetOptions.map((option) => {
                  const IconComponent = option.icon
                  return (
                    <button
                      key={option.value}
                      onClick={() => handleSelectOption('budget_range', option.value)}
                      className={`w-full p-4 rounded-xl border-2 transition-all text-left ${
                        formData.budget_range === option.value
                          ? 'border-indigo-600 bg-indigo-50 shadow-md'
                          : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <IconComponent className="w-8 h-8 text-indigo-600" />
                        <div className="flex-1">
                          <div className="font-semibold text-gray-800">{option.label}</div>
                          <div className="text-sm text-gray-600 mt-1">{option.description}</div>
                        </div>
                        {formData.budget_range === option.value && (
                          <span className="text-indigo-600 text-xl">✓</span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Step 2: Usage Type */}
          {step === 2 && (
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                <Smartphone className="w-6 h-6 text-blue-600" />
                Apa kebutuhan utama Anda?
              </h3>
              <div className="space-y-3">
                {usageOptions.map((option) => {
                  const IconComponent = option.icon
                  return (
                    <button
                      key={option.value}
                      onClick={() => handleSelectOption('usage_type', option.value)}
                      className={`w-full p-4 rounded-xl border-2 transition-all text-left ${
                        formData.usage_type === option.value
                          ? 'border-indigo-600 bg-indigo-50 shadow-md'
                          : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <IconComponent className="w-8 h-8 text-indigo-600" />
                        <div className="flex-1">
                          <div className="font-semibold text-gray-800">{option.label}</div>
                          <div className="text-sm text-gray-600 mt-1">{option.description}</div>
                        </div>
                        {formData.usage_type === option.value && (
                          <span className="text-indigo-600 text-xl">✓</span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Step 3: Data Needs */}
          {step === 3 && (
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                <Globe className="w-6 h-6 text-cyan-600" />
                Berapa banyak kuota internet yang Anda butuhkan?
              </h3>
              <div className="space-y-3">
                {dataOptions.map((option) => {
                  const IconComponent = option.icon
                  return (
                    <button
                      key={option.value}
                      onClick={() => handleSelectOption('data_needs', option.value)}
                      className={`w-full p-4 rounded-xl border-2 transition-all text-left ${
                        formData.data_needs === option.value
                          ? 'border-indigo-600 bg-indigo-50 shadow-md'
                          : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <IconComponent className="w-8 h-8 text-indigo-600" />
                        <div className="flex-1">
                          <div className="font-semibold text-gray-800">{option.label}</div>
                          <div className="text-sm text-gray-600 mt-1">{option.description}</div>
                        </div>
                        {formData.data_needs === option.value && (
                          <span className="text-indigo-600 text-xl">✓</span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Step 4: Preferred Features */}
          {step === 4 && (
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                <span className="text-yellow-500 text-2xl">⭐</span>
                Fitur apa saja yang Anda inginkan? <span className="text-sm text-gray-500">(Opsional, pilih beberapa)</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {featureOptions.map((option) => {
                  const IconComponent = option.icon
                  return (
                    <button
                      key={option.value}
                      onClick={() => handleToggleFeature(option.value)}
                      className={`p-3 rounded-lg border-2 transition-all text-left ${
                        formData.preferred_features.includes(option.value)
                          ? 'border-indigo-600 bg-indigo-50 shadow-sm'
                          : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <IconComponent className="w-5 h-5 text-indigo-600" />
                        <span className="font-medium text-gray-800 text-sm">{option.label}</span>
                        {formData.preferred_features.includes(option.value) && (
                          <span className="ml-auto text-indigo-600">✓</span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 bg-gray-50 rounded-b-2xl flex justify-between gap-3">
          <button
            onClick={step === 1 ? onClose : handleBack}
            className="px-6 py-2 text-gray-700 hover:text-gray-900 font-medium transition-colors"
            disabled={loading}
          >
            {step === 1 ? 'Skip' : 'Kembali'}
          </button>

          {step < 4 ? (
            <button
              onClick={handleNext}
              disabled={!canProceed()}
              className={`px-8 py-2 rounded-lg font-semibold transition-all ${
                canProceed()
                  ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-md hover:shadow-lg'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              Lanjut →
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-8 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg font-semibold hover:shadow-lg transition-all disabled:opacity-50"
            >
              {loading ? 'Menyimpan...' : '✨ Selesai'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default QuestionnaireModal
