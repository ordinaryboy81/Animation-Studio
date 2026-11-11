; Animation Studio - Windows installer (per-user, no administrator rights needed)
Unicode true
ManifestDPIAware true
!include "MUI2.nsh"
!define AD "Animation Studio"
!ifndef SURUM
  !define SURUM "0.0.0"  ; build.sh passes -DSURUM from the .surum file
!endif
!define ANAHTAR "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimationStudio"
Name "${AD}"
OutFile "..\cikti\Animation-Studio-Setup-${SURUM}-x64.exe"
InstallDir "$PROFILE\AnimationStudio"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${AD} ${SURUM}"
VIProductVersion "${SURUM}.0"
VIAddVersionKey "ProductName" "${AD}"
VIAddVersionKey "FileDescription" "${AD} setup"
VIAddVersionKey "FileVersion" "${SURUM}"
VIAddVersionKey "ProductVersion" "${SURUM}"
VIAddVersionKey "LegalCopyright" "MIT License"

!define MUI_ICON "..\ikon\studyo.ico"
!define MUI_UNICON "..\ikon\studyo.ico"
!define MUI_WELCOMEPAGE_TEXT "$(HOSGELDIN)"
!define MUI_FINISHPAGE_RUN "$INSTDIR\Animation Studio.exe"
!define MUI_FINISHPAGE_RUN_TEXT "$(SIMDI_AC)"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Turkish"

LangString HOSGELDIN ${LANG_ENGLISH} "A free studio for short animated videos that runs on your own computer.$\r$\n$\r$\n- No administrator rights needed; it installs into your user folder.$\r$\n- On first start it downloads the tools it needs (2-5 minutes).$\r$\n- Your projects and videos stay on this computer."
LangString HOSGELDIN ${LANG_TURKISH} "Bilgisayarında çalışan ücretsiz animasyon video stüdyosu.$\r$\n$\r$\n- Yönetici izni gerekmez, kendi kullanıcı klasörüne kurulur.$\r$\n- İlk açılışta gerekli programları internetten indirir (2-5 dk).$\r$\n- Projelerin ve videoların bu bilgisayarda kalır."
LangString SIMDI_AC ${LANG_ENGLISH} "Open Animation Studio now"
LangString SIMDI_AC ${LANG_TURKISH} "Animation Studio'yu şimdi aç"
LangString SIL_SORU ${LANG_ENGLISH} "Also delete your projects, videos and voice recordings?$\r$\n$\r$\nIf you choose No, the projects folder and your voice library stay in $INSTDIR."
LangString SIL_SORU ${LANG_TURKISH} "Projelerin, videoların ve ses kayıtların da silinsin mi?$\r$\n$\r$\nHayır dersen projeler klasörü ve ses kütüphanen $INSTDIR içinde kalır."
LangString KALDIR ${LANG_ENGLISH} "Uninstall"
LangString KALDIR ${LANG_TURKISH} "Kaldır"
LangString PROJELER ${LANG_ENGLISH} "Projects folder"
LangString PROJELER ${LANG_TURKISH} "Projeler klasörü"

Function .onInit
  !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  SetOverwrite on
  File /r "..\cikti\win\*.*"
  CreateDirectory "$INSTDIR\projeler"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\${AD}.lnk" "$INSTDIR\Animation Studio.exe"
  CreateDirectory "$SMPROGRAMS\${AD}"
  CreateShortcut "$SMPROGRAMS\${AD}\${AD}.lnk" "$INSTDIR\Animation Studio.exe"
  CreateShortcut "$SMPROGRAMS\${AD}\$(PROJELER).lnk" "$INSTDIR\projeler"
  CreateShortcut "$SMPROGRAMS\${AD}\$(KALDIR).lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${ANAHTAR}" "DisplayName" "${AD}"
  WriteRegStr HKCU "${ANAHTAR}" "DisplayVersion" "${SURUM}"
  WriteRegStr HKCU "${ANAHTAR}" "DisplayIcon" "$INSTDIR\Animation Studio.exe"
  WriteRegStr HKCU "${ANAHTAR}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${ANAHTAR}" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKCU "${ANAHTAR}" "NoModify" 1
  WriteRegDWORD HKCU "${ANAHTAR}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "$(SIL_SORU)" IDYES hepsi
    RMDir /r "$INSTDIR\motor"
    RMDir /r "$INSTDIR\fontlar"
    RMDir /r "$INSTDIR\veri"
    RMDir /r "$INSTDIR\araclar"
    RMDir /r "$INSTDIR\bin"
    RMDir /r "$INSTDIR\.ortam"
    RMDir /r "$INSTDIR\.python"
    RMDir /r "$INSTDIR\.uv_cache"
    RMDir /r "$INSTDIR\__pycache__"
    RMDir /r "$INSTDIR\tts\env"
    RMDir /r "$INSTDIR\tts\env_old"
    RMDir /r "$INSTDIR\tts\env_new"
    RMDir /r "$INSTDIR\tts\model"
    Delete "$INSTDIR\*.py"
    Delete "$INSTDIR\*.md"
    Delete "$INSTDIR\*.yaml"
    Delete "$INSTDIR\*.txt"
    Delete "$INSTDIR\*.cmd"
    Delete "$INSTDIR\*.exe"
    Delete "$INSTDIR\LICENSE"
    Delete "$INSTDIR\.surum"
    Goto kisayol
  hepsi:
    RMDir /r "$INSTDIR"
  kisayol:
  Delete "$DESKTOP\${AD}.lnk"
  RMDir /r "$SMPROGRAMS\${AD}"
  DeleteRegKey HKCU "${ANAHTAR}"
SectionEnd
