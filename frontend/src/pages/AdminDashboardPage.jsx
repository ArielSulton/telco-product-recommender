import React, { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Navigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import EmptyState from '../components/EmptyState'
import { Users, TrendingUp, Package, Edit, Trash2, Plus, Save, RefreshCw, DollarSign, AlertTriangle, BookOpen, MessageSquare, CheckCircle } from 'lucide-react'
import api from '../services/api'

const emptyProductForm = {
  name: '',
  price: '',
  quota: '',
  benefit: '',
  recommendationCategory: '',
  tags: '',
  includeRecommendation: true,
}

const getErrorMessage = (error) => {
  return error.response?.data?.detail || error.message || 'Unknown error'
}

const parseTags = (value) => {
  return value
    .split(',')
    .map(tag => tag.trim())
    .filter(Boolean)
}

const complaintCategoryLabels = {
  jaringan: 'Jaringan',
  harga_paket: 'Harga Paket',
  kuota: 'Kuota',
  pembelian: 'Pembelian',
  layanan: 'Layanan',
  lainnya: 'Lainnya',
}

const complaintStatusLabels = {
  open: 'Open',
  reviewed: 'Reviewed',
  resolved: 'Resolved',
}

const mapProductToPackage = (product) => ({
  id: product.product_id,
  name: product.product_name,
  benefit: product.benefit,
  price: product.price,
  quota: Math.round((product.quota_data_mb || 0) / 1024),
  product_id: product.product_id,
  quota_mb: product.quota_data_mb,
  recommendationCategory: product.kategori_rekomendasi || '',
  tags: product.tags || [],
  includeRecommendation: product.ikut_rekomendasi !== false,
})

const AdminDashboardPage = () => {
  const { user } = useAuth()
  const toast = useToast()

  // State for stats
  const [stats, setStats] = useState({
    total_users: 0,
    total_purchases: 0,
    total_revenue: 0,
    avg_data_usage_gb: 0,
    active_products: 0
  })

  // User recommendations data from API
  const [recommendations, setRecommendations] = useState([])
  const [loadingRecommendations, setLoadingRecommendations] = useState(true)
  const [complaints, setComplaints] = useState([])
  const [loadingComplaints, setLoadingComplaints] = useState(true)

  // Products data from API
  const [packages, setPackages] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  const [editingId, setEditingId] = useState(null)
  const [formData, setFormData] = useState(emptyProductForm)

  // Fetch user recommendations
  const fetchUserRecommendations = useCallback(async () => {
    setLoadingRecommendations(true)
    try {
      const response = await api.get('/admin/user-recommendations?limit=10')
      setRecommendations(response.data || [])
    } catch (error) {
      console.error('Failed to fetch user recommendations:', error)
      setRecommendations([])
    } finally {
      setLoadingRecommendations(false)
    }
  }, [])

  const fetchComplaints = useCallback(async () => {
    setLoadingComplaints(true)
    try {
      const response = await api.get('/admin/complaints?limit=10')
      setComplaints(response.data || [])
    } catch (error) {
      console.error('Failed to fetch complaints:', error)
      setComplaints([])
    } finally {
      setLoadingComplaints(false)
    }
  }, [])

  // Fetch products and stats from API
  const fetchProductsAndStats = useCallback(async () => {
    setLoading(true)
    try {
      // Fetch products
      const productsResponse = await api.get('/admin/products')
      const products = productsResponse.data || []

      // Map to frontend format
      const mappedProducts = products.map(mapProductToPackage)

      setPackages(mappedProducts)

      // Fetch stats
      const statsResponse = await api.get('/admin/stats')
      setStats(statsResponse.data)

      // Fetch user recommendations
      await fetchUserRecommendations()
      await fetchComplaints()

    } catch (error) {
      console.error('Failed to fetch admin data:', error)
      toast.error('Gagal memuat data admin')
    } finally {
      setLoading(false)
    }
  }, [toast, fetchUserRecommendations, fetchComplaints])

  // Fetch products and stats on mount
  useEffect(() => {
    fetchProductsAndStats()
  }, [fetchProductsAndStats])

  // Redirect if not admin (after all hooks)
  if (!user || user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  // Sync products (refresh from database)
  const handleSyncProducts = async () => {
    setSyncing(true)
    try {
      await fetchProductsAndStats()
      toast.success('Produk berhasil di-sync dari database!')
    } catch (error) {
      console.error('Sync failed:', error)
      toast.error('Gagal sync produk')
    } finally {
      setSyncing(false)
    }
  }

  // Handle form input
  const handleInputChange = (e) => {
    const { name, value, checked, type } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }))
  }

  const buildProductPayload = () => {
    const quotaGb = Number(formData.quota)
    const tags = parseTags(formData.tags)

    return {
      product_name: formData.name.trim(),
      product_family: formData.recommendationCategory,
      quota_data_mb: Math.round(quotaGb * 1024),
      validity_days: 30,
      price: parseInt(formData.price, 10),
      kategori_rekomendasi: formData.recommendationCategory,
      tags,
      ikut_rekomendasi: formData.includeRecommendation,
      benefit: formData.benefit.trim() || undefined,
      metadata: {
        benefit: formData.benefit.trim() || undefined,
      },
    }
  }

  const validateProductForm = () => {
    if (!formData.name.trim() || !formData.price || !formData.quota || !formData.recommendationCategory) {
      toast.error('Mohon isi nama, harga, kuota, dan kategori rekomendasi')
      return false
    }

    if (Number(formData.price) <= 0 || Number(formData.quota) < 0) {
      toast.error('Harga harus lebih dari 0 dan kuota tidak boleh negatif')
      return false
    }

    return true
  }

  // Add new package
  const handleAddPackage = async () => {
    // Validate form
    if (!validateProductForm()) {
      return
    }

    try {
      const response = await api.post('/admin/products', buildProductPayload())

      // Add to local state
      const newPackage = mapProductToPackage(response.data)
      setPackages([...packages, newPackage])

      // Reset form
      setFormData(emptyProductForm)
      toast.success('Produk berhasil ditambahkan!')
    } catch (error) {
      console.error('Failed to add product:', error)
      toast.error('Gagal menambahkan produk: ' + getErrorMessage(error))
    }
  }

  // Edit package
  const handleEdit = (pkg) => {
    setEditingId(pkg.id)
    setFormData({
      name: pkg.name,
      price: pkg.price.toString(),
      quota: pkg.quota.toString(),
      benefit: pkg.benefit || '',
      recommendationCategory: pkg.recommendationCategory || '',
      tags: (pkg.tags || []).join(', '),
      includeRecommendation: pkg.includeRecommendation,
    })
  }

  // Update package
  const handleUpdate = async () => {
    if (!editingId) return

    // Validate form
    if (!validateProductForm()) {
      return
    }

    try {
      const response = await api.put(`/admin/products/${editingId}`, buildProductPayload())

      // Update local state
      setPackages(packages.map(pkg =>
        pkg.id === editingId
          ? mapProductToPackage(response.data)
          : pkg
      ))

      // Reset form
      setEditingId(null)
      setFormData(emptyProductForm)
      toast.success('Produk berhasil diupdate!')
    } catch (error) {
      console.error('Failed to update product:', error)
      toast.error('Gagal mengupdate produk: ' + getErrorMessage(error))
    }
  }

  // Delete package
  const handleDelete = async (id) => {
    if (window.confirm('Apakah Anda yakin ingin menghapus produk ini?')) {
      try {
        await api.delete(`/admin/products/${id}`)

        // Remove from local state
        setPackages(packages.filter(pkg => pkg.id !== id))
        toast.success('Produk berhasil dihapus!')
      } catch (error) {
        console.error('Failed to delete product:', error)
        const errorMsg = getErrorMessage(error)

        if (errorMsg.includes('purchase')) {
          toast.error('Tidak bisa menghapus produk yang sudah dibeli user')
        } else {
          toast.error('Gagal menghapus produk: ' + errorMsg)
        }
      }
    }
  }

  const handleComplaintStatusUpdate = async (id, nextStatus) => {
    try {
      const response = await api.put(`/admin/complaints/${id}`, {
        status: nextStatus,
      })
      setComplaints(complaints.map(complaint =>
        complaint.id === id ? response.data : complaint
      ))
      toast.success('Status keluhan diperbarui')
    } catch (error) {
      console.error('Failed to update complaint:', error)
      toast.error('Gagal memperbarui status keluhan')
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-8 animate-fade-in">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Admin Dashboard</h1>
        </div>

        {/* Stats Cards */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="card animate-pulse">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-gray-200 rounded-full"></div>
                  <div className="flex-1 space-y-2">
                    <div className="h-3 bg-gray-200 rounded w-24"></div>
                    <div className="h-6 bg-gray-200 rounded w-16"></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <div className="card hover-lift glass-card border-2 border-green-200">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-green-100 rounded-full">
                    <Users className="w-6 h-6 text-green-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">TOTAL USERS</h3>
                    <p className="text-2xl font-bold text-gray-900">{stats.total_users.toLocaleString()}</p>
                  </div>
                </div>
              </div>

              <div className="card hover-lift glass-card border-2 border-cyan-200">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-cyan-100 rounded-full">
                    <TrendingUp className="w-6 h-6 text-cyan-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">AVG DATA USAGE</h3>
                    <p className="text-2xl font-bold text-gray-900">{stats.avg_data_usage_gb.toFixed(1)} GB</p>
                  </div>
                </div>
              </div>

              <div className="card hover-lift glass-card border-2 border-purple-200">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-purple-100 rounded-full">
                    <Package className="w-6 h-6 text-purple-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">TOTAL PURCHASES</h3>
                    <p className="text-2xl font-bold text-gray-900">{stats.total_purchases.toLocaleString()}</p>
                  </div>
                </div>
              </div>

              <div className="card hover-lift glass-card border-2 border-yellow-200">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-yellow-100 rounded-full">
                    <DollarSign className="w-6 h-6 text-yellow-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">TOTAL REVENUE</h3>
                    <p className="text-2xl font-bold text-gray-900">Rp {(stats.total_revenue / 1000).toFixed(0)}K</p>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* User Recommendations Table */}
        <section className="mb-8">
          <div className="card">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">User Recommendations</h2>

            {loadingRecommendations ? (
              <div className="animate-pulse space-y-3">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="h-12 bg-gray-200 rounded"></div>
                ))}
              </div>
            ) : recommendations.length === 0 ? (
              <EmptyState
                type="analytics"
                title="Belum Ada Pengguna"
                description="Sistem rekomendasi akan menampilkan penawaran personal untuk pengguna berdasarkan aktivitas dan preferensi mereka."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b-2 border-gray-200">
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Username</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Phone</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Profil Rekomendasi</th>
                      <th className="px-4 py-3 text-center font-bold text-gray-900">Purchases</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Recommended</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recommendations.map((rec, index) => (
                      <tr key={rec.user_id} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                        <td className="px-4 py-3 text-gray-900 font-medium">{rec.username}</td>
                        <td className="px-4 py-3 text-gray-600 font-mono text-sm">{rec.phone}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col gap-1">
                            <span className="text-sm font-semibold text-gray-900">
                              {rec.recommendation_class || '-'}
                            </span>
                            <span className="text-xs text-green-700">{rec.recommendation_source}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-center text-gray-900">{rec.total_purchases}</td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-sm font-medium">
                            {rec.recommended_product}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* User Complaints Table */}
        <section className="mb-8">
          <div className="card">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                <MessageSquare className="w-6 h-6 text-cyan-600" />
                Keluhan Pengguna
              </h2>
              <button
                onClick={fetchComplaints}
                className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg transition-colors"
              >
                <RefreshCw className="w-5 h-5" />
                Refresh
              </button>
            </div>

            {loadingComplaints ? (
              <div className="animate-pulse space-y-3">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="h-12 bg-gray-200 rounded"></div>
                ))}
              </div>
            ) : complaints.length === 0 ? (
              <EmptyState
                type="analytics"
                title="Belum Ada Keluhan"
                description="Keluhan pengguna akan muncul di sini dan menjadi sinyal tambahan untuk rekomendasi retensi."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b-2 border-gray-200">
                      <th className="px-4 py-3 text-left font-bold text-gray-900">User</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Kategori</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Keluhan</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Status</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Tanggal</th>
                      <th className="px-4 py-3 text-center font-bold text-gray-900">Aksi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {complaints.map((complaint, index) => (
                      <tr key={complaint.id} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                        <td className="px-4 py-3">
                          <div className="flex flex-col">
                            <span className="font-medium text-gray-900">{complaint.username || '-'}</span>
                            <span className="text-xs text-gray-500 font-mono">{complaint.phone || '-'}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-900">
                          {complaintCategoryLabels[complaint.category] || complaint.category}
                        </td>
                        <td className="px-4 py-3 text-gray-700 max-w-md">
                          <p className="line-clamp-2">{complaint.message}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            complaint.status === 'resolved'
                              ? 'bg-green-100 text-green-800'
                              : complaint.status === 'reviewed'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {complaintStatusLabels[complaint.status] || complaint.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-600 text-sm">
                          {new Date(complaint.created_at).toLocaleString('id-ID')}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <div className="inline-flex gap-2">
                            <button
                              onClick={() => handleComplaintStatusUpdate(complaint.id, 'reviewed')}
                              disabled={complaint.status !== 'open'}
                              className="inline-flex items-center gap-1 px-3 py-1 bg-blue-500 hover:bg-blue-600 text-white rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              <MessageSquare className="w-4 h-4" />
                              Review
                            </button>
                            <button
                              onClick={() => handleComplaintStatusUpdate(complaint.id, 'resolved')}
                              disabled={complaint.status === 'resolved'}
                              className="inline-flex items-center gap-1 px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              <CheckCircle className="w-4 h-4" />
                              Selesai
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* Manage Data Packages */}
        <section>
          <div className="card">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Manage Data Packages</h2>
              <button
                onClick={handleSyncProducts}
                disabled={syncing}
                className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`} />
                {syncing ? 'Syncing...' : 'Sync Products'}
              </button>
            </div>

            {/* Packages Table */}
            {packages.length === 0 ? (
              <div className="mb-8">
                <EmptyState
                  type="products"
                  action={handleSyncProducts}
                  actionLabel="Sync Products dari Database"
                />
              </div>
            ) : (
              <div className="overflow-x-auto mb-8">
                <table className="w-full">
                  <thead>
                    <tr className="border-b-2 border-gray-200">
                      <th className="px-4 py-3 text-left font-bold text-gray-900">No</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Data Packages Name</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Benefit</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Rekomendasi</th>
                      <th className="px-4 py-3 text-center font-bold text-gray-900">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {packages.map((pkg, index) => (
                      <tr key={pkg.id} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                        <td className="px-4 py-3 text-gray-900">{index + 1}.</td>
                        <td className="px-4 py-3 text-gray-900">{pkg.name}</td>
                        <td className="px-4 py-3 text-gray-900">{pkg.benefit}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col gap-1">
                            <span className="text-sm font-semibold text-gray-900">
                              {pkg.recommendationCategory || '-'}
                            </span>
                            <span className={`text-xs font-semibold ${pkg.includeRecommendation ? 'text-green-700' : 'text-gray-500'}`}>
                              {pkg.includeRecommendation ? 'Ikut rekomendasi' : 'Nonaktif rekomendasi'}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <button
                            onClick={() => handleEdit(pkg)}
                            className="inline-flex items-center gap-1 px-3 py-1 bg-cyan-500 hover:bg-cyan-600 text-white rounded mr-2 transition-colors"
                          >
                            <Edit className="w-4 h-4" />
                            EDIT
                          </button>
                          <button
                            onClick={() => handleDelete(pkg.id)}
                            className="inline-flex items-center gap-1 px-3 py-1 bg-red-500 hover:bg-red-600 text-white rounded transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                            HAPUS
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Add/Edit Package Form */}
            <div className="border-t-2 border-gray-200 pt-6">
              <h3 className="text-xl font-bold text-gray-900 mb-4">
                {editingId ? 'Edit Package' : 'Add New Package'}
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Nama Paket</label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., Paket Hemat"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Harga (Rp)</label>
                  <input
                    type="number"
                    name="price"
                    value={formData.price}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., 50000"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Kuota Data (GB)</label>
                  <input
                    type="number"
                    name="quota"
                    value={formData.quota}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., 15"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Kategori Rekomendasi</label>
                  <select
                    name="recommendationCategory"
                    value={formData.recommendationCategory}
                    onChange={handleInputChange}
                    className="input-field"
                  >
                    <option value="">Pilih kategori</option>
                    <option value="data">Data</option>
                    <option value="combo">Combo</option>
                    <option value="voice">Voice</option>
                    <option value="starter">Starter</option>
                    <option value="premium">Premium</option>
                    <option value="retention">Retention</option>
                  </select>
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Benefit Tambahan</label>
                  <input
                    type="text"
                    name="benefit"
                    value={formData.benefit}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., + Chat, + Youtube"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Tags Rekomendasi</label>
                  <input
                    type="text"
                    name="tags"
                    value={formData.tags}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., youth, budget, streaming"
                  />
                </div>

                <div className="flex items-center gap-3 pt-8">
                  <input
                    id="includeRecommendation"
                    type="checkbox"
                    name="includeRecommendation"
                    checked={formData.includeRecommendation}
                    onChange={handleInputChange}
                    className="w-5 h-5 accent-cyan-600"
                  />
                  <label htmlFor="includeRecommendation" className="text-gray-700 font-semibold">
                    Ikut rekomendasi
                  </label>
                </div>
              </div>

              <div className="flex gap-3">
                {editingId ? (
                  <>
                    <button
                      onClick={handleUpdate}
                      className="btn-primary inline-flex items-center gap-2 active-press"
                    >
                      <Save className="w-5 h-5" />
                      Update
                    </button>
                    <button
                      onClick={() => {
                        setEditingId(null)
                        setFormData(emptyProductForm)
                      }}
                      className="btn-secondary active-press"
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    onClick={handleAddPackage}
                    className="btn-primary inline-flex items-center gap-2 active-press"
                  >
                    <Plus className="w-5 h-5" />
                    Simpan
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ML Model Management */}
        <section className="mt-8">
          <div className="card">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">ML Model Management</h2>

            <div className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-6 mb-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-8 h-8 text-yellow-600 flex-shrink-0 mt-1" />
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-yellow-900 mb-2">Model Operations</h3>
                  <p className="text-yellow-800">
                    Model Random Forest v2 aktif digunakan untuk rekomendasi.
                    Monitoring pipeline dan eksperimen model tersedia melalui layanan pendukung berikut.
                  </p>
                  <div className="mt-4 space-y-2 text-sm">
                    <p className="text-yellow-700">
                      <span className="font-semibold">Airflow UI:</span> http://localhost:8080 (username: airflow, password: airflow)
                    </p>
                    <p className="text-yellow-700">
                      <span className="font-semibold">MLflow UI:</span> http://localhost:5000
                    </p>
                    <p className="text-yellow-800">
                      <span className="font-semibold">Status:</span> Pengelolaan retraining dari dashboard admin belum tersedia.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="border-2 border-gray-200 rounded-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">Model Status</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-700">Current Model:</span>
                    <span className="font-semibold text-gray-900">Random Forest v2</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Training Source:</span>
                    <span className="font-semibold text-gray-900">Kaggle Telco Churn</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Status:</span>
                    <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-semibold">
                      Active
                    </span>
                  </div>
                </div>
              </div>

              <div className="border-2 border-gray-200 rounded-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">Manual Retraining</h3>
                <p className="text-gray-700 mb-4 text-sm">
                  Trigger manual model retraining outside of scheduled runs.
                  Requires Airflow service to be running.
                </p>
                <button
                  disabled
                  className="w-full btn-primary inline-flex items-center justify-center gap-2 opacity-50 cursor-not-allowed"
                >
                  <RefreshCw className="w-5 h-5" />
                  Trigger Retraining (Coming Soon)
                </button>
              </div>
            </div>

            <div className="mt-6 border-2 border-blue-200 bg-blue-50 rounded-lg p-6">
              <h3 className="text-lg font-bold text-blue-900 mb-3 flex items-center gap-2">
                <BookOpen className="w-5 h-5" />
                Model Information
              </h3>
              <div className="space-y-2 text-sm text-blue-800">
                <p><span className="font-semibold">Algorithm:</span> Random Forest classifier</p>
                <p><span className="font-semibold">Input Features:</span> 21 behavioral and engineered features</p>
                <p><span className="font-semibold">Recommendation Classes:</span> 6 package categories</p>
                <p><span className="font-semibold">Evaluation:</span> 86.8% accuracy and 99.57% top-3 accuracy</p>
                <p><span className="font-semibold">Product Matching:</span> Active products ranked using recommendation category and tags</p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default AdminDashboardPage
