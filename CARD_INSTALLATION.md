# Curve Control Custom Card Installation Guide

## Overview
The Curve Control integration includes a custom dashboard card that provides an interactive interface for viewing and controlling your energy optimization schedule.

## Automatic Installation (Preferred Method)

When you install the integration, it will automatically:
1. Create the directory `config/www/curve_control/`  
2. Copy `curve-control-card.js` to that directory
3. Provide setup instructions in the Home Assistant logs

## Manual Resource Registration (Required)

After installation, you need to register the card as a frontend resource:

1. **Go to Settings → Dashboards → Resources**
2. **Click "Add Resource"**
3. **Enter the following details:**
   - **URL:** `/local/curve_control/curve-control-card.js`
   - **Type:** `JavaScript Module`
4. **Click "Create"**
5. **Refresh your browser** (Ctrl+F5)

## Adding the Card to Your Dashboard

1. **Edit your dashboard** (click the three dots → Edit Dashboard)
2. **Add a new card** (click "Add Card")
3. **Select "Manual" card type**
4. **Enter the following YAML:**

```yaml
type: custom:curve-control-card
entity: sensor.curve_control_status
```

5. **Save the card**

## Card Features

The custom card provides three tabs:

### 🏠 Dashboard Tab
- Toggle optimization on/off
- View current savings and status
- Interactive temperature schedule chart
- Real-time updates during optimization

### ⚙️ Basic Settings Tab
- Home size configuration
- Target temperature setting
- Location/rate plan selection
- Time away/home schedule
- Savings level (comfort vs savings trade-off)

### 📅 Detailed Schedule Tab
- 24-hour custom temperature schedule
- Set high/low temperature limits for each hour
- Advanced users can create complex schedules

## Troubleshooting

### Card Not Showing Up
1. Verify the resource was added correctly in Settings → Dashboards → Resources
2. Check that the URL is exactly: `/local/curve_control/curve-control-card.js`
3. Ensure the file exists at `config/www/curve_control/curve-control-card.js`
4. Clear browser cache and refresh (Ctrl+F5)

### Card Shows "Custom element doesn't exist"
1. Ensure resource type is set to "JavaScript Module" (not "JavaScript")
2. Check browser console for JavaScript errors
3. Verify the integration is installed and running

### Settings Not Saving
1. Check Home Assistant logs for errors
2. Verify the `curve_control.update_schedule` service exists
3. Ensure backend connectivity is working

## File Locations

- **Integration:** `config/custom_components/curve_control/`
- **Card File:** `config/www/curve_control/curve-control-card.js`
- **Log Messages:** Check Settings → System → Logs

## Getting Help

If you encounter issues:
1. Check the Home Assistant logs for Curve Control messages
2. Verify all entities are available (`switch.curve_control_use_optimized_temperatures`, etc.)
3. Test the backend connectivity
4. Create an issue on the GitHub repository with log details