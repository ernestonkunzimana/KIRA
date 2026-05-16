# 🎨 KIRA Frontend — Visual Design Guide

## 🌈 Color Palette

```
┌─────────────────────────────────────────────────────────────┐
│ PRIMARY (Success) — GREEN                                   │
│ #22c55e  ████████████████████████████████████████████████   │
│ Used for: Buttons, success messages, active status          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SECONDARY (Info) — BLUE                                     │
│ #3b82f6  ████████████████████████████████████████████████   │
│ Used for: Links, secondary actions, info messages           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ DANGER (Error) — RED                                        │
│ #ef4444  ████████████████████████████████████████████████   │
│ Used for: Errors, alerts, anomalies                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ WARNING — YELLOW                                            │
│ #eab308  ████████████████████████████████████████████████   │
│ Used for: Warnings, cautions                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ BACKGROUND (Dark) — NEAR BLACK                              │
│ #0f1117  ████████████████████████████████████████████████   │
│ Used for: Main page background                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ CARD (Dark Gray) — DARKER GRAY                              │
│ #1a1f35  ████████████████████████████████████████████████   │
│ Used for: Cards, modals, containers                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ BORDER — SLATE GRAY                                         │
│ #334155  ████████████████████████████████████████████████   │
│ Used for: Borders, dividers, subtle lines                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ TEXT (Light) — OFF WHITE                                    │
│ #e2e8f0  ████████████████████████████████████████████████   │
│ Used for: Primary text, headings                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ TEXT (Muted) — LIGHT GRAY                                   │
│ #94a3b8  ████████████████████████████████████████████████   │
│ Used for: Secondary text, captions                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📱 Layout Wireframes

### Login Page
```
┌─────────────────────────────────────────────┐
│                                             │
│                 🔋 KIRA                     │
│       Kigali Intelligent Resilience Agent   │
│                                             │
│  ╔═════════════════════════════════════╗   │
│  ║   🔐 Secure Access                 ║   │
│  ║                                     ║   │
│  ║  Client ID:  [_______________]    ║   │
│  ║  Password:   [_______________]    ║   │
│  ║  ☑ Remember me  Forgot password?    ║   │
│  ║                                     ║   │
│  ║  [🔓 SIGN IN]                      ║   │
│  ║                                     ║   │
│  ║  Don't have an account?             ║   │
│  ║  > Create new account               ║   │
│  ╚═════════════════════════════════════╝   │
│                                             │
│  🔐 Enterprise-grade JWT authentication    │
│                                             │
└─────────────────────────────────────────────┘
```

### Signup Page
```
┌─────────────────────────────────────────────┐
│                                             │
│                 🔋 KIRA                     │
│                                             │
│  ╔═════════════════════════════════════╗   │
│  ║   📋 Create Account                 ║   │
│  ║                                     ║   │
│  ║  ▼ Personal Information              ║   │
│  ║  First Name: [___]  Last Name: [__] ║   │
│  ║  Email: [___________________]       ║   │
│  ║                                     ║   │
│  ║  ▼ Organization                     ║   │
│  ║  Organization: [_______________]    ║   │
│  ║  Department: [_______________]      ║   │
│  ║  Role: [_______________]            ║   │
│  ║                                     ║   │
│  ║  ▼ Account Credentials              ║   │
│  ║  Client ID: [_______________]       ║   │
│  ║  Password: [_______________]        ║   │
│  ║  Confirm: [_______________]         ║   │
│  ║                                     ║   │
│  ║  [✅ Create]  [← Back]               ║   │
│  ╚═════════════════════════════════════╝   │
│                                             │
└─────────────────────────────────────────────┘
```

### Dashboard
```
┌──────────────────────────────────────────────────────────────┐
│  🔋 KIRA | Command Center              🚪 Logout            │
├──────────────────────────────────────────────────────────────┤
│ SIDEBAR             │  MAIN CONTENT                          │
│                     │                                        │
│ 👤 Session         │  System Health Status                  │
│ ─────────────────  │  ┌─────┬─────┬─────┬─────┐            │
│ dashboard          │  │🟢 OK│🟢 OK│🟢 OK│🟢 OK│            │
│ operator           │  │API  │ML   │Cache│DB   │            │
│                     │  └─────┴─────┴─────┴─────┘            │
│ 📍 Active Assets   │                                        │
│ Gasabo-A (Solar)   │  🗺️ Live Tower Map                     │
│ Nyarugenge-A       │  ┌────────────────────────┐            │
│ Kicukiro-A         │  │  [Interactive Map]     │            │
│                     │  │  • Solar towers (🟢)    │            │
│ ⚡ Manual Override  │  │  • Generator (🟡)      │            │
│ Tower: [Select]    │  └────────────────────────┘            │
│ Action: [Select]   │                                        │
│ Reason: [___]      │  Domain-Specific Analysis              │
│ [⚡ Execute]       │  ┌────────┬─────────┬──────────┐      │
│                     │  │📡 IoT  │⚡ Grid  │⚙️ Gens   │      │
│                     │  ├────────┼─────────┼──────────┤      │
│                     │  │ Sliders │ Sliders │ Sliders  │      │
│                     │  │ [...]   │ [...]   │ [...]    │      │
│                     │  │ [Run]   │ [Run]   │ [Run]    │      │
│                     │  └────────┴─────────┴──────────┘      │
│                     │                                        │
│                     │  📋 Audit Trail                        │
│                     │  [Event logs and metrics]              │
│                     │                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎯 Component Styles

### Button — Primary (Green)
```
    [🔓 SIGN IN]
    
    Normal State:
    ┌─────────────────┐
    │  🔓 SIGN IN     │  #22c55e gradient
    │                 │  Padding: 12px 16px
    │                 │  Rounded: 8px
    └─────────────────┘
    
    Hover State:
    ┌─────────────────┐
    │  🔓 SIGN IN     │  Darker green
    │                 │  Lifted 2px (shadow)
    │                 │  Opacity: 0.9
    └─────────────────┘
    
    Active State:
    ┌─────────────────┐
    │  🔓 SIGN IN     │  Pressed effect
    └─────────────────┘
```

### Card — Metric
```
    ┌────────────────────┐
    │  🟢 OK             │  Gradient background
    │  API Gateway       │  Border: 1px #334155
    │  ────────────────  │  Rounded: 12px
    │  ✅ Operational    │  Padding: 18px
    └────────────────────┘
    
    Hover:
    ┌────────────────────┐
    │  🟢 OK             │  Border: #22c55e
    │  API Gateway       │  Shadow glow
    │  ────────────────  │  Lifted 4px
    │  ✅ Operational    │
    └────────────────────┘
```

### Input Field
```
    Label: Client ID
    ┌──────────────────────────┐
    │ [________________]       │  Normal: #334155 border
    └──────────────────────────┘   BG: rgba(#0f1117, 0.5)
    
    Focused:
    ┌──────────────────────────┐
    │ [________________]       │  Border: #22c55e
    └──────────────────────────┘   BG: rgba(#22c55e, 0.05)
                                   Shadow: 0 0 0 3px rgba(#22c55e, 0.1)
```

### Status Badges
```
    ✅ OK / Active
    ┌──────────┐
    │  🟢 OK   │  Background: rgba(#22c55e, 0.2)
    └──────────┘  Text: #22c55e (green)
    
    ⚠️  Warning
    ┌──────────┐
    │  🟡 WARN │  Background: rgba(#eab308, 0.2)
    └──────────┘  Text: #eab308 (yellow)
    
    ❌ Error
    ┌──────────┐
    │  🔴 FAIL │  Background: rgba(#ef4444, 0.2)
    └──────────┘  Text: #ef4444 (red)
```

---

## 📐 Typography

```
H1 (Page Title)         Font: 2.5rem  Weight: 700  Color: #e2e8f0
H2 (Section)            Font: 2rem    Weight: 700  Color: #e2e8f0
H3 (Subsection)         Font: 1.5rem  Weight: 700  Color: #e2e8f0
H4 (Minor Heading)      Font: 1.2rem  Weight: 600  Color: #e2e8f0

Body Text               Font: 1rem    Weight: 400  Color: #e2e8f0
Secondary Text          Font: 0.9rem  Weight: 400  Color: #94a3b8
Caption                 Font: 0.85rem Weight: 500  Color: #94a3b8
Label                   Font: 0.95rem Weight: 600  Color: #e2e8f0

Metric Value (Large)    Font: 1.8rem  Weight: 700  Color: #22c55e
Metric Label (Small)    Font: 0.85rem Weight: 500  Color: #94a3b8

Code / Monospace        Font: 0.9rem  Family: monospace  Color: #e2e8f0
```

---

## ✨ Animations

### Fade In
```
Duration: 0.4s
Timing: ease-out
From: opacity 0
To: opacity 1
Used for: Messages, alerts
```

### Slide In
```
Duration: 0.6s
Timing: ease-out
From: transform translateY(20px), opacity 0
To: transform translateY(0), opacity 1
Used for: Modal/card entry
```

### Hover Lift
```
Duration: 0.3s
Timing: ease
Transform: translateY(-4px)
Shadow: 0 8px 16px rgba(0,0,0,0.3)
Used for: Cards, buttons
```

---

## 🎬 User Flows

### Authentication Flow
```
START
  │
  ├─→ Is User Authenticated? ─→ NO ─→ Show Auth Gate
  │                                       │
  │                                       ├─→ "Login" Button?
  │                                       │   └─→ Show Login Form
  │                                       │       └─→ Valid? ─→ Get Token
  │                                       │                    └─→ Store in Session
  │                                       │                        └─→ Redirect to Dashboard
  │                                       │
  │                                       └─→ "Sign Up" Button?
  │                                           └─→ Show Signup Form
  │                                               └─→ Valid? ─→ Register User
  │                                                            └─→ Redirect to Login
  │
  └─→ YES ─→ Show Dashboard ─→ [Load Data] ─→ [Display UI]
```

### Prediction Flow
```
User selects Domain (IoT/Grid/Generators)
  │
  ├─→ Domain Tab Loads ─→ Display Input Sliders
  │
  ├─→ User Adjusts Sliders
  │
  ├─→ User Clicks "Run Analysis"
  │
  ├─→ Show Spinner "Running ensemble inference..."
  │
  ├─→ Send POST /api/v1/predict/{domain}
  │   with sensor_data + auth token
  │
  ├─→ Backend Processes ─→ Returns JSON Result
  │
  ├─→ Display Results:
  │   ├─ Decision badge (✅/⚠️/🔒)
  │   ├─ Confidence metric
  │   ├─ Anomaly score
  │   ├─ Feature importance chart
  │
  └─→ Done ─→ User can adjust sliders and re-run
```

---

## 🔗 Component Hierarchy

```
App
├── AuthenticationGate (if not authenticated)
│   ├── LoginPage
│   │   ├── BrandHeader
│   │   ├── LoginForm
│   │   │   ├── ClientIDInput
│   │   │   ├── PasswordInput
│   │   │   ├── RememberCheckbox
│   │   │   └── SubmitButton
│   │   └── SignupLink
│   │
│   └── SignupPage
│       ├── BrandHeader
│       ├── SignupForm
│       │   ├── PersonalSection
│       │   │   ├── FirstNameInput
│       │   │   ├── LastNameInput
│       │   │   └── EmailInput
│       │   ├── OrganizationSection
│       │   │   ├── OrgInput
│       │   │   ├── DepartmentSelect
│       │   │   └── RoleSelect
│       │   ├── CredentialsSection
│       │   │   ├── ClientIDInput
│       │   │   ├── PasswordInput
│       │   │   └── ConfirmPasswordInput
│       │   └── SubmitButton
│       └── LoginLink
│
└── Dashboard (if authenticated)
    ├── Header
    │   ├── Brand Logo + Title
    │   └── LogoutButton
    │
    ├── Sidebar
    │   ├── SessionInfo
    │   ├── ActiveAssets
    │   └── ManualOverridePanel
    │
    └── MainContent
        ├── SystemHealthCards
        │   ├── APICard
        │   ├── MLCard
        │   ├── RedisCard
        │   └── DatabaseCard
        │
        ├── TowerMap
        │   └── PydeckMap
        │
        ├── AnalysisTabs
        │   ├── IoTTab
        │   │   ├── SensorSliders
        │   │   └── ResultsPanel
        │   │       ├── DecisionBadge
        │   │       ├── Metrics
        │   │       └── SHAPChart
        │   │
        │   ├── GridTab (similar structure)
        │   │
        │   └── GeneratorTab (similar structure)
        │
        └── AuditTrailSection
            ├── FilterPanel
            ├── Metrics
            └── EventTable
```

---

## 🎨 CSS Classes Reference

```
.auth-container       ← Login/signup card wrapper
.form-group          ← Input field container
.form-group input    ← Input styling
.btn                 ← Base button
.btn-primary         ← Green primary button
.btn-secondary       ← Outlined secondary button
.metric-card         ← Metric display card
.metric-value        ← Large metric number
.metric-label        ← Metric title
.status-badge        ← Status indicator
.status-ok           ← Green status
.status-warning      ← Yellow status
.status-error        ← Red status
.alert               ← Alert message
.alert-success       ← Green alert
.alert-error         ← Red alert
.alert-info          ← Blue alert
.brand-header        ← Header with logo
.brand-icon          ← Logo element
.brand-title         ← Main title
.tab                 ← Tab button
.tab.active          ← Active tab
.link-text           ← Secondary text with link
```

---

## 🔧 Responsive Breakpoints

```
Mobile          max-width: 480px    ← Phone
Tablet          max-width: 768px    ← iPad
Laptop          min-width: 1024px   ← Desktop
Large Desktop   min-width: 1920px   ← 4K

Adjustments:
• Sidebar: Collapse on mobile
• Cards: Stack vertically on tablet
• Fonts: Reduce size slightly on mobile
• Padding: Reduce margins on mobile
```

---

**End of Design Guide**
