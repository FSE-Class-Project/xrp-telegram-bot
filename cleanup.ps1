#!/usr/bin/env powershell
# XRP Bot Cleanup Script - PowerShell Version

Write-Host "🧹 Cleaning up XRP Bot processes..." -ForegroundColor Yellow

# Method 1: Kill all Python processes
Write-Host "Stopping Python processes..." -ForegroundColor Cyan
try {
    Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Python processes stopped" -ForegroundColor Green
} catch {
    Write-Host "⚠️  No Python processes found or already stopped" -ForegroundColor Yellow
}

# Method 2: Kill processes using port 8000
Write-Host "Freeing port 8000..." -ForegroundColor Cyan
try {
    $port8000 = netstat -ano | Select-String ":8000.*LISTENING"
    if ($port8000) {
        $pids = ($port8000 | ForEach-Object { ($_ -split '\s+')[-1] }) | Sort-Object -Unique
        foreach ($pid in $pids) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "  Killed process $pid" -ForegroundColor Gray
        }
        Write-Host "✅ Port 8000 freed" -ForegroundColor Green
    } else {
        Write-Host "✅ Port 8000 already free" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️  Could not check port 8000" -ForegroundColor Yellow
}

# Wait for cleanup
Start-Sleep -Seconds 2

# Verify cleanup
Write-Host "`nVerifying cleanup..." -ForegroundColor Cyan

$pythonProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcs) {
    Write-Host "⚠️  Warning: Some Python processes still running:" -ForegroundColor Yellow
    $pythonProcs | ForEach-Object { Write-Host "  PID $($_.Id): $($_.ProcessName)" -ForegroundColor Gray }
} else {
    Write-Host "✅ All Python processes stopped" -ForegroundColor Green
}

$port8000Check = netstat -ano | Select-String ":8000.*LISTENING"
if ($port8000Check) {
    Write-Host "⚠️  Warning: Port 8000 still in use" -ForegroundColor Yellow
} else {
    Write-Host "✅ Port 8000 is free" -ForegroundColor Green
}

Write-Host "`n🚀 Ready to run: python run.py" -ForegroundColor Green
Write-Host "=" * 50