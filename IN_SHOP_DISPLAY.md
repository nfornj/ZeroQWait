# In-Shop Display Feature

## Overview

The In-Shop Display is a dedicated view designed to show real-time queue information on a large screen (TV/monitor) within your shop. This helps customers see the current wait times and who's being served without needing to ask staff.

## Key Features

- **Real-time Updates**: Queue information refreshes every 3 seconds automatically
- **Large, Clear Display**: Optimized for viewing from a distance
- **Now Serving Section**: Prominently displays customers currently being served
- **Queue Statistics**: Shows total people waiting and estimated wait time
- **Waiting List**: Displays up to 8 customers in the queue with position numbers
- **Live Clock**: Shows current time and date
- **Custom Branding**: Uses your shop's logo and primary color scheme

## How to Use

### 1. Access the Display

From your Shop Dashboard:
- Look for the **"In-Shop Display"** button
- Click it to open the display in a new browser tab
- The URL format is: `http://localhost:3000/display/{shopId}`

From Queue Management Page:
- Click the **"Open Display"** button in the info alert at the top

### 2. Setup on a TV/Monitor

**Option A: Using a Computer**
1. Connect a computer to your TV/monitor via HDMI
2. Open a web browser (Chrome, Firefox, Safari)
3. Navigate to the display URL
4. Press F11 to enter fullscreen mode
5. The display will automatically refresh and update

**Option B: Using a Smart TV**
1. Open the web browser on your Smart TV
2. Navigate to the display URL
3. Enter fullscreen mode if available

**Option C: Using a Tablet**
1. Open Safari (iPad) or Chrome (Android) on your tablet
2. Navigate to the display URL
3. Add to home screen for easy access
4. Tap "Add" to create a fullscreen app-like experience

### 3. Display Layout

The in-shop display is divided into several sections:

**Header (Top)**
- Shop logo and name
- Current date and time

**Main Content**
- **Left Panel**: "NOW SERVING" - Shows who is currently being served with large, easy-to-read position numbers
- **Right Panel Top**: Queue statistics (number waiting, estimated wait time)
- **Right Panel Bottom**: List of waiting customers with position numbers

**Footer**
- Instructions for customers to join the queue online

## Display Information

### What Customers See

1. **Currently Being Served**: Large display showing the position number and name of customers being served
2. **People Waiting**: Total count of customers in the queue
3. **Estimated Wait Time**: Calculated based on average service time × number of people ahead
4. **Next Customers**: First 8 people in the queue, with "Up Next" badges for the first 2
5. **How to Join**: URL for customers to join the queue from their phones

### Auto-Refresh Behavior

- Queue data refreshes every **3 seconds**
- Clock updates every **1 second**
- No manual refresh needed
- Display stays active as long as the browser tab is open

## Best Practices

### Display Setup
- **Position**: Place the screen where customers can easily see it (near entrance or waiting area)
- **Size**: Use at least a 32" screen for optimal visibility
- **Height**: Mount at eye level or slightly above
- **Lighting**: Avoid direct sunlight or glare on the screen

### Maintenance
- Keep the browser tab open and in fullscreen mode
- Restart the display daily to ensure optimal performance
- Ensure stable internet connection for real-time updates
- Consider using a dedicated device to avoid interruptions

### Customer Experience
- **Reduce Confusion**: Customers can see their position without asking
- **Manage Expectations**: Real-time wait times help customers decide if they can wait
- **Encourage Online Check-in**: Footer shows the URL for remote queue joining
- **Build Trust**: Transparency in queue status improves customer satisfaction

## Troubleshooting

### Display Not Updating
- Check internet connection
- Refresh the browser page
- Verify the shop has an active queue

### Display Looks Wrong
- Try a different browser (Chrome recommended)
- Clear browser cache
- Check screen resolution settings
- Verify the shopId in the URL is correct

### Performance Issues
- Close other browser tabs
- Restart the computer/device
- Update the web browser to the latest version

## Technical Details

### URL Format
```
http://localhost:3000/display/{shopId}
```

Replace `{shopId}` with your actual shop ID number.

### Browser Compatibility
- Chrome (recommended)
- Firefox
- Safari
- Edge
- Any modern web browser with JavaScript enabled

### Screen Resolutions
Optimized for:
- 1920x1080 (Full HD)
- 1366x768 (HD)
- Works on any resolution, but HD or higher recommended

## Privacy Considerations

- Only shows customer first names (or partial names provided)
- No phone numbers or email addresses displayed
- Position numbers are randomly assigned per queue session
- No sensitive information is visible to other customers

## Feature Enhancements Coming Soon

- [ ] Multiple queue support (for shops with multiple service providers)
- [ ] Customizable display themes and layouts
- [ ] Sound notifications when next customer is called
- [ ] QR code for easy queue joining
- [ ] Multi-language support

## Support

For technical support or feature requests, please contact your system administrator or refer to the main documentation.
