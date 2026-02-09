# Lark SPA Rendering Fix Strategies

## Strategy 1: Extended Wait + Scroll Trigger
- Wait 10-15 seconds for full initialization
- Scroll the sidebar area to trigger lazy loading
- Click on specific UI elements to force render

## Strategy 2: Mobile Version
- Try mobile web version: https://m.larksuite.com
- Often simpler, more compatible with automation

## Strategy 3: Alternative Entry Points
- Start from Lark notification email links
- Use direct conversation URLs if known
- Access via calendar or docs page first

## Strategy 4: JavaScript Injection
- Use browser_task's evaluate to:
  - Force re-render: `window.dispatchEvent(new Event('resize'))`
  - Check React/Vue state: `__REACT_DEVTOOLS_GLOBAL_HOOK__`
  - Trigger data fetch manually

## Strategy 5: Lark Open API (Recommended for Production)
- Register bot app at open.larksuite.com
- Use webhook for message events
- More reliable than browser automation

## Strategy 6: Desktop App Bridge
- Lark desktop app may expose local API
- Or use OS-level automation (pyautogui, etc)

## Current Status
- Profile "Google Chrome - Adam" works for login
- Tenant: fg9w9yu3odc.sg.larksuite.com
- Issue: Message list not populating in web UI
- Cost per attempt: ~$0.06-0.08

## Next Test
Try Strategy 2 (mobile) or Strategy 4 (JS injection)
