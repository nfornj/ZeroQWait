// Hand landmark indices from MediaPipe Hands
export const HAND_LANDMARKS = {
  WRIST: 0,
  THUMB_CMC: 1,
  THUMB_MCP: 2,
  THUMB_IP: 3,
  THUMB_TIP: 4,
  INDEX_FINGER_MCP: 5,
  INDEX_FINGER_PIP: 6,
  INDEX_FINGER_DIP: 7,
  INDEX_FINGER_TIP: 8,
  MIDDLE_FINGER_MCP: 9,
  MIDDLE_FINGER_PIP: 10,
  MIDDLE_FINGER_DIP: 11,
  MIDDLE_FINGER_TIP: 12,
  RING_FINGER_MCP: 13,
  RING_FINGER_PIP: 14,
  RING_FINGER_DIP: 15,
  RING_FINGER_TIP: 16,
  PINKY_MCP: 17,
  PINKY_PIP: 18,
  PINKY_DIP: 19,
  PINKY_TIP: 20,
};

export interface Landmark {
  x: number;
  y: number;
  z: number;
}

export interface GestureResult {
  gesture: string;
  fingerCount: number;
  confidence: number;
  emoji: string;
}

// Check if a finger is extended
const isFingerExtended = (
  landmarks: Landmark[],
  fingerTip: number,
  fingerPip: number,
  fingerMcp: number
): boolean => {
  const tip = landmarks[fingerTip];
  const pip = landmarks[fingerPip];
  const mcp = landmarks[fingerMcp];

  // Finger is extended if tip is higher (lower y value) than pip and mcp
  return tip.y < pip.y && tip.y < mcp.y;
};

// Check if thumb is extended
const isThumbExtended = (landmarks: Landmark[], handLabel: string): boolean => {
  const thumbTip = landmarks[HAND_LANDMARKS.THUMB_TIP];
  const thumbIp = landmarks[HAND_LANDMARKS.THUMB_IP];
  const thumbMcp = landmarks[HAND_LANDMARKS.THUMB_MCP];
  const indexMcp = landmarks[HAND_LANDMARKS.INDEX_FINGER_MCP];

  // For right hand, thumb extends to the right; for left hand, to the left
  if (handLabel === 'Right') {
    return thumbTip.x < thumbIp.x && thumbTip.x < thumbMcp.x;
  } else {
    return thumbTip.x > thumbIp.x && thumbTip.x > thumbMcp.x;
  }
};

// Count extended fingers
export const countFingers = (landmarks: Landmark[], handLabel: string): number => {
  let count = 0;

  // Check thumb
  if (isThumbExtended(landmarks, handLabel)) {
    count++;
  }

  // Check other fingers
  const fingers = [
    { tip: HAND_LANDMARKS.INDEX_FINGER_TIP, pip: HAND_LANDMARKS.INDEX_FINGER_PIP, mcp: HAND_LANDMARKS.INDEX_FINGER_MCP },
    { tip: HAND_LANDMARKS.MIDDLE_FINGER_TIP, pip: HAND_LANDMARKS.MIDDLE_FINGER_PIP, mcp: HAND_LANDMARKS.MIDDLE_FINGER_MCP },
    { tip: HAND_LANDMARKS.RING_FINGER_TIP, pip: HAND_LANDMARKS.RING_FINGER_PIP, mcp: HAND_LANDMARKS.RING_FINGER_MCP },
    { tip: HAND_LANDMARKS.PINKY_TIP, pip: HAND_LANDMARKS.PINKY_PIP, mcp: HAND_LANDMARKS.PINKY_MCP },
  ];

  fingers.forEach((finger) => {
    if (isFingerExtended(landmarks, finger.tip, finger.pip, finger.mcp)) {
      count++;
    }
  });

  return count;
};

// Recognize specific gestures
export const recognizeGesture = (
  landmarks: Landmark[],
  handLabel: string
): GestureResult => {
  const fingerCount = countFingers(landmarks, handLabel);

  // Get finger states
  const thumbExtended = isThumbExtended(landmarks, handLabel);
  const indexExtended = isFingerExtended(
    landmarks,
    HAND_LANDMARKS.INDEX_FINGER_TIP,
    HAND_LANDMARKS.INDEX_FINGER_PIP,
    HAND_LANDMARKS.INDEX_FINGER_MCP
  );
  const middleExtended = isFingerExtended(
    landmarks,
    HAND_LANDMARKS.MIDDLE_FINGER_TIP,
    HAND_LANDMARKS.MIDDLE_FINGER_PIP,
    HAND_LANDMARKS.MIDDLE_FINGER_MCP
  );
  const ringExtended = isFingerExtended(
    landmarks,
    HAND_LANDMARKS.RING_FINGER_TIP,
    HAND_LANDMARKS.RING_FINGER_PIP,
    HAND_LANDMARKS.RING_FINGER_MCP
  );
  const pinkyExtended = isFingerExtended(
    landmarks,
    HAND_LANDMARKS.PINKY_TIP,
    HAND_LANDMARKS.PINKY_PIP,
    HAND_LANDMARKS.PINKY_MCP
  );

  const thumbTip = landmarks[HAND_LANDMARKS.THUMB_TIP];
  const thumbIp = landmarks[HAND_LANDMARKS.THUMB_IP];
  const indexTip = landmarks[HAND_LANDMARKS.INDEX_FINGER_TIP];
  const middleTip = landmarks[HAND_LANDMARKS.MIDDLE_FINGER_TIP];
  const wrist = landmarks[HAND_LANDMARKS.WRIST];

  // Thumbs Up - thumb extended up, others closed
  if (
    thumbExtended &&
    !indexExtended &&
    !middleExtended &&
    !ringExtended &&
    !pinkyExtended &&
    thumbTip.y < wrist.y
  ) {
    return { gesture: 'Thumbs Up', fingerCount, confidence: 0.95, emoji: '👍' };
  }

  // Thumbs Down - thumb extended down, others closed
  if (
    thumbExtended &&
    !indexExtended &&
    !middleExtended &&
    !ringExtended &&
    !pinkyExtended &&
    thumbTip.y > wrist.y
  ) {
    return { gesture: 'Thumbs Down', fingerCount, confidence: 0.95, emoji: '👎' };
  }

  // Peace Sign - index and middle extended, others closed
  if (
    !thumbExtended &&
    indexExtended &&
    middleExtended &&
    !ringExtended &&
    !pinkyExtended
  ) {
    return { gesture: 'Peace', fingerCount, confidence: 0.9, emoji: '✌️' };
  }

  // OK Sign - thumb and index forming circle
  const thumbIndexDistance = Math.sqrt(
    Math.pow(thumbTip.x - indexTip.x, 2) + Math.pow(thumbTip.y - indexTip.y, 2)
  );
  if (
    thumbIndexDistance < 0.05 &&
    middleExtended &&
    ringExtended &&
    pinkyExtended
  ) {
    return { gesture: 'OK', fingerCount, confidence: 0.85, emoji: '👌' };
  }

  // Rock On / I Love You - index and pinky extended
  if (
    !middleExtended &&
    !ringExtended &&
    indexExtended &&
    pinkyExtended
  ) {
    if (thumbExtended) {
      return { gesture: 'I Love You', fingerCount, confidence: 0.9, emoji: '🤟' };
    }
    return { gesture: 'Rock On', fingerCount, confidence: 0.9, emoji: '🤘' };
  }

  // Pointing - only index extended
  if (
    !thumbExtended &&
    indexExtended &&
    !middleExtended &&
    !ringExtended &&
    !pinkyExtended
  ) {
    return { gesture: 'Pointing', fingerCount, confidence: 0.9, emoji: '☝️' };
  }

  // Open Hand / High Five - all fingers extended
  if (fingerCount === 5) {
    return { gesture: 'Open Hand', fingerCount, confidence: 0.95, emoji: '🖐️' };
  }

  // Fist - no fingers extended
  if (fingerCount === 0) {
    return { gesture: 'Fist', fingerCount, confidence: 0.95, emoji: '✊' };
  }

  // Number gestures (1-5)
  const numberEmojis = ['', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣'];
  return {
    gesture: `Number ${fingerCount}`,
    fingerCount,
    confidence: 0.85,
    emoji: numberEmojis[fingerCount] || '🤚',
  };
};
