#!/bin/bash
# kubectl wrapper that falls back to sudo if permission denied

kubectl "$@" 2>/dev/null || sudo kubectl "$@"
