param([Parameter(Mandatory=$true)][string]$Video)
$ErrorActionPreference = 'Stop'
$script:exitCode = 0
$script:opened = $false
try {
    Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
    if (-not (Test-Path -LiteralPath $Video -PathType Leaf)) { exit 2 }
    [xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="ConXml — Bienvenido" Width="1060" Height="680" MinWidth="600" MinHeight="420"
        Background="#F5F6FA" WindowStartupLocation="CenterScreen">
  <Grid Background="Black">
    <MediaElement x:Name="Player" Stretch="Uniform" LoadedBehavior="Manual"
                  UnloadedBehavior="Close" Volume="1"/>
    <Button x:Name="Skip" Content="Saltar" Width="100" Height="36"
            HorizontalAlignment="Right" VerticalAlignment="Bottom" Margin="0,0,22,20"
            Background="#F5F6FA" Foreground="#17213A" FontSize="15" FontWeight="SemiBold"/>
  </Grid>
</Window>
'@
    $window = [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $xaml))
    $player = $window.FindName('Player')
    $window.Width = [Math]::Min(1060, [Windows.SystemParameters]::WorkArea.Width - 40)
    $window.Height = [Math]::Min(680, [Windows.SystemParameters]::WorkArea.Height - 40)
    $window.MinWidth = [Math]::Min(600, $window.Width)
    $window.MinHeight = [Math]::Min(420, $window.Height)
    $window.FindName('Skip').Add_Click({ $player.Stop(); $window.Close() })
    $player.Add_MediaOpened({ $script:opened = $true })
    $player.Add_MediaEnded({ $player.Stop(); $window.Close() })
    $player.Add_MediaFailed({ $script:exitCode = 2; $window.Close() })
    $timer = New-Object Windows.Threading.DispatcherTimer
    $timer.Interval = [TimeSpan]::FromSeconds(15)
    $timer.Add_Tick({
        $timer.Stop()
        if (-not $script:opened) { $script:exitCode = 2; $window.Close() }
    })
    $window.Add_Loaded({
        $timer.Start()
        $player.Source = [Uri]::new([IO.Path]::GetFullPath($Video))
        $player.Play()
    })
    $window.Add_Closed({ $timer.Stop(); $player.Close() })
    $null = $window.ShowDialog()
    exit $script:exitCode
} catch { exit 2 }
