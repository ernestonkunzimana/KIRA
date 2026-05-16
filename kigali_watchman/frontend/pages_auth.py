"""
KIRA Frontend: Login & Signup Pages
Clean, modern authentication UI with complete form validation.
"""

import streamlit as st
from kira_auth import (
    authenticate_user, register_user, verify_registration, is_valid_email, is_strong_password
)
from styles import THEME, GLOBAL_CSS


def render_login_page():
    """Render the login page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    
    col_l, col_m, col_r = st.columns([1, 1.5, 1])
    
    with col_m:
        # Brand Header
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 40px; position: relative; z-index: 1;">
            <div style="width:72px; height:72px; margin:0 auto 12px auto;">
                <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" width="72" height="72" aria-hidden="true">
                    <rect x="40" y="70" width="120" height="60" rx="8" fill="#ffffff" opacity="0.98"/>
                    <rect x="146" y="82" width="6" height="36" fill="#ffffff" opacity="0.98"/>
                    <circle cx="100" cy="36" r="18" fill="#ffd166" opacity="0.98"/>
                    <path d="M20 150 C48 130 88 160 128 140 C168 120 208 150 248 140" transform="translate(-20,0)" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity="0.9"/>
                </svg>
            </div>
            <h1 style="margin: 0 0 4px 0;">KIRA</h1>
            <p style="color: {THEME['text_muted']}; margin: 0; font-size: 24px; line-height: 1.2;">
                Kigali Intelligent Resilient Agency
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {THEME['card_bg']} 0%, #1e293b 100%);
            border: 1px solid {THEME['border']};
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        ">
        """, unsafe_allow_html=True)
        
        st.markdown("### 🔐 Secure Access", help="Login with your KIRA credentials")
        
        # Login Form
        with st.form("login_form", clear_on_submit=False):
            client_id = st.text_input(
                "Client ID / Username",
                placeholder="e.g., dashboard, sensor_gateway, ops_team",
                help="Your unique KIRA client identifier"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your secure password",
                help="Your KIRA account password"
            )
            
            col1, col2 = st.columns([1, 1])
            with col1:
                remember_me = st.checkbox("Remember me", value=False)
            with col2:
                st.markdown(f'<div style="text-align: right; padding-top: 8px;">' + 
                           f'<a href="#" style="color: {THEME["text_muted"]}; font-size: 0.85rem;">Forgot password?</a></div>',
                           unsafe_allow_html=True)
            
            st.divider()
            
            submit_btn = st.form_submit_button(
                "🔓 Sign In",
                use_container_width=True,
                type="primary"
            )
        
        if submit_btn:
            if not client_id or not password:
                st.error("❌ Please enter both Client ID and Password")
            else:
                with st.spinner("🔐 Verifying credentials..."):
                    success, token, error = authenticate_user(client_id, password)
                
                if success:
                    st.session_state.authenticated = True
                    st.session_state.token = token
                    st.session_state.client_id = client_id
                    st.session_state.user_role = "operator"  # Default role
                    from datetime import datetime
                    st.session_state.login_time = datetime.now()
                    
                    st.success(f"✅ Welcome, {client_id}! Redirecting to dashboard...")
                    st.balloons()
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ {error}")

        if st.session_state.get("pending_client_id"):
            st.markdown("---")
            st.markdown("### 🛡️ Verify Existing Account")
            st.caption("Enter the verification code you received by email or SMS to finish signup.")

            with st.form("inline_verify_form", clear_on_submit=False):
                verify_client_id = st.text_input(
                    "Client ID / Username",
                    value=st.session_state.get("pending_client_id", ""),
                    help="Use the client ID you created during signup",
                )
                verify_code = st.text_input(
                    "Verification Code",
                    placeholder="Enter your 6-digit code",
                    help="Use the code from your email or phone message",
                )

                verify_submit = st.form_submit_button(
                    "✅ Confirm Account",
                    use_container_width=True,
                    type="primary",
                )

            if verify_submit:
                if not verify_client_id or not verify_code:
                    st.error("❌ Client ID and verification code are required")
                else:
                    with st.spinner("🔐 Confirming your account..."):
                        success, _, error = verify_registration(verify_client_id, verify_code)

                    if success:
                        pending_password = st.session_state.get("pending_password")
                        if pending_password:
                            auth_ok, token, auth_error = authenticate_user(verify_client_id, pending_password)
                            if auth_ok:
                                st.session_state.authenticated = True
                                st.session_state.token = token
                                st.session_state.client_id = verify_client_id
                                st.session_state.user_role = "operator"
                                from datetime import datetime
                                st.session_state.login_time = datetime.now()
                                st.session_state.pending_client_id = None
                                st.session_state.pending_password = None
                                st.session_state.pending_verification_code = None
                                st.success("✅ Account verified and access granted")
                                st.balloons()
                                st.rerun()
                            else:
                                st.success("✅ Account verified. Please sign in now.")
                                st.session_state.pending_client_id = None
                                st.session_state.pending_verification_code = None
                                st.session_state.current_page = "login"
                                st.rerun()
                        else:
                            st.success("✅ Account verified. Please sign in now.")
                            st.session_state.pending_client_id = None
                            st.session_state.pending_verification_code = None
                            st.session_state.current_page = "login"
                            st.rerun()
                    else:
                        st.error(f"❌ {error}")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Signup Prompt
        st.markdown(f"""
        <div style="text-align: center; margin-top: 24px; padding: 16px; 
                    background: rgba(34, 197, 94, 0.05); border-radius: 8px;
                    border: 1px solid {THEME['border']};">
            <p style="color: {THEME['text_muted']}; margin: 0; font-size: 0.9rem;">
                Don't have an account? 
                <strong style="color: {THEME['primary']}; cursor: pointer;">
                    <a href="#" style="color: {THEME['primary']};">Create new account</a>
                </strong>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Footer
        st.markdown(f"""
        <div style="text-align: center; margin-top: 40px; padding-top: 24px; 
                    border-top: 1px solid {THEME['border']};">
            <p style="color: {THEME['text_muted']}; font-size: 0.75rem; margin: 0;">
                🔐 Enterprise-grade security with JWT authentication & audit trail
            </p>
            <p style="color: {THEME['text_muted']}; font-size: 0.75rem; margin: 4px 0 0 0;">
                KIRA v2.4.0 | © 2024 Kigali Infrastructure Authority
            </p>
        </div>
        """, unsafe_allow_html=True)


def render_signup_page():
    """Render the signup/registration page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    
    col_l, col_m, col_r = st.columns([1, 1.5, 1])
    
    with col_m:
        # Brand Header
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 40px; position: relative; z-index: 1;">
            <div style="width:72px; height:72px; margin:0 auto 12px auto;">
                <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" width="72" height="72" aria-hidden="true">
                    <rect x="40" y="70" width="120" height="60" rx="8" fill="#ffffff" opacity="0.98"/>
                    <rect x="146" y="82" width="6" height="36" fill="#ffffff" opacity="0.98"/>
                    <circle cx="100" cy="36" r="18" fill="#ffd166" opacity="0.98"/>
                    <path d="M20 150 C48 130 88 160 128 140 C168 120 208 150 248 140" transform="translate(-20,0)" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity="0.9"/>
                </svg>
            </div>
            <h1 style="margin: 0 0 4px 0;">KIRA</h1>
            <p style="color: {THEME['text_muted']}; margin: 0; font-size: 0.95rem;">
                Kigali Intelligent Resilience Agent
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {THEME['card_bg']} 0%, #1e293b 100%);
            border: 1px solid {THEME['border']};
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        ">
        """, unsafe_allow_html=True)
        
        st.markdown("### 📋 Create Account", help="Register for KIRA access")
        
        # Signup Form
        with st.form("signup_form", clear_on_submit=False):
            st.markdown("**Personal Information**", help="Your basic details")
            
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input(
                    "First Name",
                    placeholder="John",
                    help="Your first name"
                )
            with col2:
                last_name = st.text_input(
                    "Last Name",
                    placeholder="Doe",
                    help="Your last name"
                )
            
            email = st.text_input(
                "Email Address",
                placeholder="john.doe@example.com",
                help="Your corporate email"
            )
            
            st.markdown("**Organization**", help="Your organization details")
            
            organization = st.text_input(
                "Organization Name",
                placeholder="e.g., Rwanda National Grid Authority",
                help="Your organization or agency"
            )
            
            department = st.selectbox(
                "Department",
                [
                    "Select Department",
                    "Operations",
                    "Maintenance",
                    "Engineering",
                    "Infrastructure",
                    "IT Support",
                    "Management",
                    "Other"
                ],
                help="Your department"
            )
            
            role = st.selectbox(
                "Role/Position",
                [
                    "Select Role",
                    "System Operator",
                    "Technician",
                    "Engineer",
                    "Manager",
                    "Administrator",
                    "Analyst",
                    "Other"
                ],
                help="Your job role"
            )
            
            st.markdown("**Account Credentials**", help="Create your login credentials")
            
            client_id = st.text_input(
                "Client ID / Username",
                placeholder="e.g., john.doe_ops",
                help="Unique identifier for KIRA access"
            )
            
            phone = st.text_input(
                "Phone Number (Optional)",
                placeholder="+250 7XX XXX XXX",
                help="Your contact number"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Create a strong password",
                help="Minimum 8 characters with uppercase, lowercase, digit, and special character"
            )
            
            password_confirm = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Re-enter your password",
                help="Must match your password"
            )
            
            st.markdown("**Preferences**", help="Your notification preferences")
            
            col1, col2 = st.columns(2)
            with col1:
                receive_alerts = st.checkbox("Receive System Alerts", value=True)
            with col2:
                receive_reports = st.checkbox("Receive Daily Reports", value=True)
            
            terms_accepted = st.checkbox(
                "I agree to the Terms of Service and Privacy Policy",
                value=False,
                help="You must accept the terms to continue"
            )
            
            st.divider()
            
            col1, col2 = st.columns(2)
            with col1:
                submit_btn = st.form_submit_button(
                    "✅ Create Account",
                    use_container_width=True,
                    type="primary"
                )
            with col2:
                cancel_btn = st.form_submit_button(
                    "← Back to Login",
                    use_container_width=True
                )
        
        if cancel_btn:
            st.session_state.current_page = "login"
            st.rerun()
        
        if submit_btn:
            # Validation
            errors = []
            
            if not first_name or not last_name:
                errors.append("❌ First and Last name are required")
            
            if not email or not is_valid_email(email):
                errors.append("❌ Valid email address is required")
            
            if not organization or organization == "":
                errors.append("❌ Organization name is required")
            
            if department == "Select Department":
                errors.append("❌ Please select a department")
            
            if role == "Select Role":
                errors.append("❌ Please select a role")
            
            if not client_id or len(client_id) < 3:
                errors.append("❌ Client ID must be at least 3 characters")
            
            if not password or len(password) < 8:
                errors.append("❌ Password must be at least 8 characters")
            
            if password != password_confirm:
                errors.append("❌ Passwords do not match")
            
            if not terms_accepted:
                errors.append("❌ You must accept the Terms of Service")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Check password strength
                is_strong, strength_msg = is_strong_password(password)
                if not is_strong:
                    st.warning(f"⚠️ {strength_msg}")
                else:
                    # Attempt registration
                    user_data = {
                        "client_id": client_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "password": password,
                        "organization": organization,
                        "department": department,
                        "role": role,
                        "phone": phone if phone else None,
                        "receive_alerts": receive_alerts,
                        "receive_reports": receive_reports,
                    }
                    
                    with st.spinner("📝 Creating your account..."):
                        success, user_id, error, details = register_user(user_data)

                    if success:
                        st.success(f"✅ Account created successfully! Your Client ID is: **{user_id}**")
                        st.session_state.pending_client_id = user_id
                        st.session_state.pending_password = password
                        st.session_state.current_page = "verify"
                        if details and details.get("verification_required"):
                            channels = details.get("channels", [])
                            channel_text = " or ".join(channels).upper() if channels else "EMAIL/SMS"
                            st.info(
                                f"📨 Verification code sent via {channel_text}. Use either channel to confirm your account before signing in."
                            )
                            if details.get("delivery_pending") and details.get("verification_code"):
                                st.warning(f"Development verification code: {details.get('verification_code')}")
                        else:
                            st.info("📧 A confirmation message has been sent to your contact details.")
                        st.balloons()
                        st.session_state.current_page = "login"
                        st.rerun()
                    else:
                        st.error(f"❌ Registration failed: {error}")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Already have account
        st.markdown(f"""
        <div style="text-align: center; margin-top: 24px;">
            <p style="color: {THEME['text_muted']}; margin: 0; font-size: 0.9rem;">
                Already have an account? 
                <strong style="color: {THEME['primary']}; cursor: pointer;">
                    <a href="#" style="color: {THEME['primary']};">Sign in here</a>
                </strong>
            </p>
        </div>
        """, unsafe_allow_html=True)


def render_verify_page():
    """Render the account verification page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    col_l, col_m, col_r = st.columns([1, 1.5, 1])

    with col_m:
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 32px; position: relative; z-index: 1;">
            <div style="width:72px; height:72px; margin:0 auto 12px auto;">
                <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" width="72" height="72" aria-hidden="true">
                    <rect x="40" y="70" width="120" height="60" rx="8" fill="#ffffff" opacity="0.98"/>
                    <rect x="146" y="82" width="6" height="36" fill="#ffffff" opacity="0.98"/>
                    <circle cx="100" cy="36" r="18" fill="#ffd166" opacity="0.98"/>
                    <path d="M20 150 C48 130 88 160 128 140 C168 120 208 150 248 140" transform="translate(-20,0)" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity="0.9"/>
                </svg>
            </div>
            <h1 style="margin: 0 0 4px 0;">KIRA</h1>
            <p style="color: {THEME['text_muted']}; margin: 0; font-size: 0.95rem;">
                Confirm your account to enter the command center
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {THEME['card_bg']} 0%, #1e293b 100%);
            border: 1px solid {THEME['border']};
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        ">
        """, unsafe_allow_html=True)

        st.markdown("### 🛡️ Verify Account", help="Enter the code sent to your email or phone")

        client_id = st.session_state.get("pending_client_id") or st.text_input(
            "Client ID / Username",
            placeholder="Enter the client ID you just registered",
        )
        code = st.text_input(
            "Verification Code",
            placeholder="Enter the code from email or SMS",
        )

        col1, col2 = st.columns(2)
        with col1:
            verify_btn = st.button("✅ Confirm Account", type="primary", use_container_width=True)
        with col2:
            back_btn = st.button("← Back to Login", use_container_width=True)

        if back_btn:
            st.session_state.current_page = "login"
            st.rerun()

        if verify_btn:
            if not client_id or not code:
                st.error("❌ Client ID and verification code are required")
            else:
                with st.spinner("🔐 Verifying account..."):
                    success, _, error = verify_registration(client_id, code)

                if success:
                    pending_password = st.session_state.get("pending_password")
                    if pending_password:
                        auth_ok, token, auth_error = authenticate_user(client_id, pending_password)
                        if auth_ok:
                            st.session_state.authenticated = True
                            st.session_state.token = token
                            st.session_state.client_id = client_id
                            st.session_state.user_role = "operator"
                            from datetime import datetime
                            st.session_state.login_time = datetime.now()
                            st.session_state.pending_client_id = None
                            st.session_state.pending_password = None
                            st.session_state.pending_verification_code = None
                            st.success("✅ Account verified and access granted")
                            st.balloons()
                            st.rerun()
                        else:
                            st.success("✅ Account verified. Please sign in now.")
                            st.session_state.current_page = "login"
                            st.rerun()
                    else:
                        st.success("✅ Account verified. Please sign in now.")
                        st.session_state.current_page = "login"
                        st.rerun()
                else:
                    st.error(f"❌ {error}")

        st.markdown("</div>", unsafe_allow_html=True)
