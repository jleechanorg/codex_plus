#!/bin/bash
# Email Setup for Codex Plus - Configuration Helper

# Auto-detect email from git config as default
DEFAULT_EMAIL="${EMAIL_USER:-$(git config user.email 2>/dev/null || echo '<your-email@example.com>')}"

echo "🔧 Setting up email configuration for Codex Plus..."
echo ""
echo "Using account: ${DEFAULT_EMAIL}"
echo ""

# Interactive email setup if not already configured
if [[ "$DEFAULT_EMAIL" == *"example.com"* ]] || [[ -z "$EMAIL_USER" ]]; then
    echo "📧 Email not configured. Set EMAIL_USER environment variable or configure git:"
    echo "   git config user.email your-email@gmail.com"
    echo ""
fi

echo "To complete email setup, you need a Gmail App Password:"
echo "1. Go to: https://myaccount.google.com/apppasswords"
echo "2. Generate app password for 'Mail' application"
echo "3. Use the 16-character password below"
echo ""
echo "Set these environment variables (replace <your-email> with your Gmail address):"
echo 'export EMAIL_USER="<your-email@gmail.com>"'
echo 'export EMAIL_PASS="your-16-char-app-password"'
echo 'export BACKUP_EMAIL="<your-email@gmail.com>"'
echo ""
echo "🔐 SECURE SETUP (RECOMMENDED):"
echo "Store credentials securely using environment variables or credential managers"
echo ""
echo "⚠️  WARNING: Never commit email credentials to version control"
echo "   - Use environment variables"
echo "   - Use secure credential storage (keychain/secret service)"
echo "   - Never store passwords in plaintext files"