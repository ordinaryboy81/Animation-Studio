; Animation Studio - Windows launcher (no console window).
; Works in two layouts:
;   installed package : bin\uv.exe + its own Python in .ortam (created on first run by kur.cmd)
;   source checkout   : uses the Python found on PATH (same as BASLAT.bat)
Unicode true
Name "Animation Studio"
OutFile "baslatici.exe"
Icon "..\ikon\studyo.ico"
RequestExecutionLevel user
SilentInstall silent
SetCompressor /SOLID lzma
VIProductVersion "1.1.0.0"
VIAddVersionKey "ProductName" "Animation Studio"
VIAddVersionKey "FileDescription" "Animation Studio"
VIAddVersionKey "FileVersion" "1.1.0"
VIAddVersionKey "LegalCopyright" "MIT License"

Section
  SetOutPath "$EXEDIR"
  IfFileExists "$EXEDIR\arayuz.py" var
    MessageBox MB_ICONSTOP "This file must stay in the Animation Studio folder, next to arayuz.py."
    Quit
  var:
  IfFileExists "$EXEDIR\bin\uv.exe" paketli sistem

  paketli:
    StrCpy $1 "$EXEDIR\.ortam\Scripts\python.exe"
    IfFileExists "$1" 0 kur
    nsExec::Exec '"$1" -c "import yaml, PIL, numpy, playwright, uv, ffmpeg"'
    Pop $0
    StrCmp $0 "0" hazir
    kur:      ; first run or missing packages: a visible window shows the download, then closes
    ExecWait '"$SYSDIR\cmd.exe" /c ""$EXEDIR\kur.cmd""' $0
    IfFileExists "$1" 0 bitti
    StrCmp $0 "0" hazir bitti

  sistem:
    IfFileExists "$EXEDIR\veri\.kisayol" kisayolTamam
      CreateDirectory "$EXEDIR\veri"
      CreateShortCut "$DESKTOP\Animation Studio.lnk" "$EXEPATH" "" "$EXEPATH" 0
      CreateShortCut "$SMPROGRAMS\Animation Studio.lnk" "$EXEPATH" "" "$EXEPATH" 0
      FileOpen $9 "$EXEDIR\veri\.kisayol" w
      FileClose $9
    kisayolTamam:
    SearchPath $1 python.exe
    StrCmp $1 "" 0 pythonVar
      MessageBox MB_ICONSTOP "Python was not found. Install Python 3.11 or newer first (see README)."
      Quit
    pythonVar:
    nsExec::Exec '"$1" -c "import yaml, PIL, numpy, playwright"'
    Pop $0
    StrCmp $0 "0" hazir
    ExecWait '"$SYSDIR\cmd.exe" /c "title Animation Studio - setup & echo Downloading the required packages, this takes a minute or two. This window closes by itself. & echo. & "$1" -m pip install -r gereksinimler.txt"'

  hazir:      ; the studio runs without a window and opens in the browser; this program ends when the studio quits
  nsExec::Exec '"$1" -X utf8 "$EXEDIR\arayuz.py" --gizli'
  Pop $0
  StrCmp $0 "0" bitti
    IfFileExists "$EXEDIR\veri\studyo.log" 0 bitti
    MessageBox MB_ICONEXCLAMATION|MB_YESNO "Animation Studio closed unexpectedly (code $0).$\n$\nOpen the log file? (veri\studyo.log)" IDNO bitti
    ExecShell "open" "$EXEDIR\veri\studyo.log"
  bitti:
SectionEnd
