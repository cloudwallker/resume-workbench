param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputPath) { throw 'Fixture output exists.' }
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($InputPath, $false, $true, $false)
    $legacyFile = [object]$OutputPath
    $legacyFormat = [object]0
    $document.SaveAs2([ref]$legacyFile, [ref]$legacyFormat)
} finally {
    try {
        if ($null -ne $document) {
            $saveDocument = [object]0
            try { $document.Close([ref]$saveDocument) } finally {
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
            }
        }
    } finally {
        if ($null -ne $word) {
            $saveApplication = [object]0
            try { $word.Quit([ref]$saveApplication) } finally {
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
            }
        }
    }
}
