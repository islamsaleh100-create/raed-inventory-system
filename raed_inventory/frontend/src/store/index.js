import { configureStore, createSlice } from '@reduxjs/toolkit'

// ─── Auth Slice ────────────────────────────────────────────────────────
const stored_user = localStorage.getItem('user')
const stored_token = localStorage.getItem('access_token')

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: stored_user ? JSON.parse(stored_user) : null,
    token: stored_token || null,
    loading: false,
    error: null,
  },
  reducers: {
    loginStart(state) { state.loading = true; state.error = null },
    loginSuccess(state, action) {
      state.loading = false
      state.user = action.payload.user
      state.token = action.payload.token
      localStorage.setItem('access_token', action.payload.token)
      localStorage.setItem('user', JSON.stringify(action.payload.user))
    },
    loginFail(state, action) {
      state.loading = false
      state.error = action.payload
    },
    logout(state) {
      state.user = null
      state.token = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
    },
    updateUser(state, action) {
      state.user = { ...state.user, ...action.payload }
      localStorage.setItem('user', JSON.stringify(state.user))
    },
  },
})

export const { loginStart, loginSuccess, loginFail, logout, updateUser } = authSlice.actions

// ─── UI Slice ──────────────────────────────────────────────────────────
const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    sidebarOpen: true,
    activeModule: 'dashboard',
  },
  reducers: {
    toggleSidebar(state) { state.sidebarOpen = !state.sidebarOpen },
    setSidebarOpen(state, action) { state.sidebarOpen = action.payload },
    setActiveModule(state, action) { state.activeModule = action.payload },
  },
})

export const { toggleSidebar, setSidebarOpen, setActiveModule } = uiSlice.actions

// ─── Store ─────────────────────────────────────────────────────────────
export const store = configureStore({
  reducer: {
    auth: authSlice.reducer,
    ui: uiSlice.reducer,
  },
})

// ─── Selectors ─────────────────────────────────────────────────────────
export const selectUser = (state) => state.auth.user
export const selectToken = (state) => state.auth.token
export const selectIsAuthenticated = (state) => !!state.auth.token
export const selectUserRoles = (state) => state.auth.user?.roles || []
export const selectSidebarOpen = (state) => state.ui.sidebarOpen

// ─── Role helpers ──────────────────────────────────────────────────────
export const hasRole = (roles, ...required) =>
  required.some(r => roles.includes(r))

export const isAdmin = (roles) => hasRole(roles, 'admin', 'super_admin')
export const isBranchUser = (roles) => hasRole(roles, 'branch_user', 'branch_manager')
export const isWarehouseUser = (roles) => hasRole(roles, 'warehouse_user', 'warehouse_manager')
export const isBranchManager = (roles) => hasRole(roles, 'branch_manager', 'admin', 'super_admin')
export const isWarehouseManager = (roles) => hasRole(roles, 'warehouse_manager', 'admin', 'super_admin')
export const isOperationsManager = (roles) => hasRole(roles, 'operations_manager', 'admin', 'super_admin')
