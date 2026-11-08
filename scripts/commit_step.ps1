param(
    [Parameter(Mandatory = $true)]
    [string]$Id,
    [Parameter(Mandatory = $true)]
    [string[]]$Files,
    [Parameter(Mandatory = $true)]
    [string]$Msg
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$protectedPrompt = [System.IO.Path]::GetFullPath(
    (Join-Path $root "PROMPT_AI_TIEP_TUC.md")
)
$protectedLogs = [System.IO.Path]::GetFullPath(
    (Join-Path $root "backend\logs")
)
$allowedFiles = @($Files | ForEach-Object { $_.Replace("\", "/") })

foreach ($path in $Files) {
    if ([System.IO.Path]::IsPathRooted($path)) {
        throw "Files must be repository-relative paths: $path"
    }
    $resolved = [System.IO.Path]::GetFullPath((Join-Path $root $path))
    if (-not $resolved.StartsWith(
            $root + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -or -not (Test-Path $resolved) -or (Get-Item $resolved).PSIsContainer) {
        throw "Expected an existing file inside the repository: $path"
    }
    if ([string]::Equals($resolved, $protectedPrompt,
            [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals($resolved, $protectedLogs,
            [System.StringComparison]::OrdinalIgnoreCase) -or
        $resolved.StartsWith($protectedLogs + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing protected path: $path"
    }
}

$initialStaged = @(& git diff --cached --name-only)
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect staged paths." }
foreach ($path in $initialStaged) {
    $normalized = $path.Replace("/", "\")
    if ($normalized -ieq "PROMPT_AI_TIEP_TUC.md" -or
        $normalized -ieq "backend\logs" -or
        $normalized.StartsWith("backend\logs\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing commit: protected path is already staged: $path"
    }
    if ($allowedFiles -notcontains $path.Replace("\", "/")) {
        throw "Refusing commit: unrelated path is already staged: $path"
    }
}

& git add -- $Files
if ($LASTEXITCODE -ne 0) { throw "git add failed." }

$staged = @(& git diff --cached --name-only)
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect staged paths." }
foreach ($path in $staged) {
    $normalized = $path.Replace("\", "/")
    if ($normalized -eq "PROMPT_AI_TIEP_TUC.md" -or
        $normalized -eq "backend/logs" -or
        $normalized.StartsWith("backend/logs/")) {
        throw "Refusing commit: protected path is staged: $path"
    }
    if ($allowedFiles -notcontains $normalized) {
        throw "Refusing commit: git staged an unlisted path: $path"
    }
}

& git commit -m "dss-opt: $Id $Msg" `
    -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
if ($LASTEXITCODE -ne 0) { throw "git commit failed." }
