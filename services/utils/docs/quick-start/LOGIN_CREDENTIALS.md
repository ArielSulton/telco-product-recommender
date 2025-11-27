# 🔐 Login Credentials - Development Mode

## Fixed Credentials untuk Demo

Frontend menggunakan **mock authentication** dengan credentials tetap untuk testing dan demo.

---

## 👤 Available Accounts:

### 1. Demo User (Regular User)
```
Phone/Username: 08123456789
Password: user123
Name: Demo User
Segment: 2 (Family Plan)
```

### 2. Admin User
```
Phone/Username: admin
Password: admin123
Name: Admin User
Segment: 1 (Premium)
```

### 3. Test User
```
Phone/Username: 08111111111
Password: demo
Name: Test User
Segment: 3 (Budget Plan)
```

---

## 🌐 Access URLs:

**Frontend**: http://localhost:5173
**Login Page**: http://localhost:5173/login
**Backend API**: http://localhost:8000/api/v1/docs

---

## 📝 Notes:

- ✅ **Password validation**: Password MUST match exactly (case-sensitive)
- ✅ **Error handling**: Invalid credentials show error message
- ⚠️ **Mock only**: Ini mock authentication, tidak ada enkripsi atau backend validation
- 🔒 **Production**: Untuk production, credentials ini harus diganti dengan sistem auth yang proper

---

## 🧪 Testing:

1. Buka http://localhost:5173/login
2. Pilih salah satu credentials di atas
3. Login → Redirect ke Dashboard
4. Cek localStorage untuk melihat token dan user data

---

## 🛠️ Customization:

Untuk menambah/edit credentials, edit file:
```
frontend/src/services/authService.js
```

Di bagian `validCredentials` array (line 83-87).

---

**Status**: ✅ Fixed credentials active
**Last Updated**: 2025-11-10
