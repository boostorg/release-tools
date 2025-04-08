
iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))

echo "You may need to close and re-open your shell window."

choco feature disable --name='ignoreInvalidOptionsSwitches'
choco install -y visualstudio2022buildtools --parameters  "--add Microsoft.VisualStudio.Component.VC.Llvm.Clang --add Microsoft.VisualStudio.Component.VC.Llvm.ClangToolset --add Microsoft.VisualStudio.ComponentGroup.NativeDesktop.Llvm.Clang --add Microsoft.VisualStudio.Component.VC.CMake.Project"
# choco install -y 7zip.install --version 22.1
# choco install -y cmake.install --installargs '\"ADD_CMAKE_TO_PATH=System\"' --version 3.27.9
# choco install -y curl --version 8.0.1
choco install -y dotnetfx --version 4.8.0.20220524
# choco install -y git.install --version 2.40.1
# choco install -y hashdeep --version 4.4
# choco install -y jq --version 1.6
# choco install -y llvm --version 16.0.3
choco install -y microsoft-build-tools --version 15.0.26320.2
# choco install -y mingw --version 12.2.0.03042023
# choco install -y notepadplusplus --version 8.5.2
# choco install -y notepadplusplus.install --version 8.5.2
# choco install -y rsync --version 6.2.8
# choco install -y ruby --version 3.1.3.1
choco install -y vcredist2017 --version 14.16.27033
# choco install -y Wget --version 1.21.3
choco install -y windows-sdk-10.1 --version 10.1.18362.1
# choco install -y winscp --version 5.21.8
# choco install -y winscp.install --version 5.21.8
choco upgrade -y visualstudio2022-workload-vctools --package-parameters "--add Microsoft.VisualStudio.Component.VC.14.34.17.4.x86.x64 --add Microsoft.VisualStudio.Component.VC.14.29.16.11.x86.x64 --add Microsoft.VisualStudio.Component.VC.v141.x86.x64 --add Microsoft.VisualStudio.Component.VC.140"

