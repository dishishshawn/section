"""
HTML email templates for Section transactional emails.
Inline CSS only — no external dependencies.
Brand colours: moss (#4A5E3A), rust (#B85C38), cream (#F5F0E8).
"""


def magic_link_html(link: str, expiry_minutes: int = 15) -> str:
    """Return a fully self-contained HTML email for the magic-link sign-in."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sign in to Section</title>
</head>
<body style="margin:0;padding:0;background-color:#F5F0E8;font-family:Georgia,serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#F5F0E8;padding:40px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:6px;
                      border:1px solid #D9D1C0;overflow:hidden;max-width:560px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background-color:#4A5E3A;padding:28px 40px;">
              <p style="margin:0;font-size:22px;font-weight:bold;
                        color:#F5F0E8;letter-spacing:0.04em;">Section</p>
              <p style="margin:4px 0 0;font-size:11px;color:#C8D8B8;
                        letter-spacing:0.08em;text-transform:uppercase;">
                Land Graph Operating Layer
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px 40px 32px;">
              <h1 style="margin:0 0 16px;font-size:20px;color:#2C3A1E;font-weight:normal;">
                Your sign-in link
              </h1>
              <p style="margin:0 0 28px;font-size:15px;line-height:1.6;color:#4A4A3A;">
                Click the button below to sign in to Section. This link expires in
                <strong>{expiry_minutes}&nbsp;minutes</strong>.
              </p>

              <!-- CTA button -->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:4px;background-color:#B85C38;">
                    <a href="{link}"
                       style="display:inline-block;padding:14px 32px;
                              font-size:15px;font-weight:bold;
                              color:#ffffff;text-decoration:none;
                              border-radius:4px;letter-spacing:0.02em;">
                      Sign in to Section
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:28px 0 0;font-size:13px;color:#7A7A6A;line-height:1.5;">
                Or copy and paste this URL into your browser:<br />
                <a href="{link}" style="color:#4A5E3A;word-break:break-all;">{link}</a>
              </p>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <hr style="border:none;border-top:1px solid #E8E0D0;margin:0;" />
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px 32px;">
              <p style="margin:0;font-size:12px;color:#9A9A8A;line-height:1.6;">
                If you didn&rsquo;t request this sign-in link, you can safely ignore this
                email &mdash; no account changes will be made. This link can only be used
                once and will expire automatically.
              </p>
              <p style="margin:12px 0 0;font-size:12px;color:#9A9A8A;">
                &copy; Section &mdash; Land Graph Operating Layer
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
