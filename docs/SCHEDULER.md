# 스케줄러 등록 (T8)

매일 아침 08:00에 `scripts/collect.py`를 실행한다.

## 등록

PowerShell에서 실행 (관리자 권한 불필요):

```powershell
$py   = "C:\Users\user\anaconda3\envs\radar\python.exe"
$root = "C:\Users\user\Desktop\lee\AI_Rader"
$name = "AI_Radar_Collect"

$action  = New-ScheduledTaskAction -Execute $py -Argument "scripts\collect.py" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At 8:00am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Description "Personal AI Radar daily collection (arxiv, github, huggingface)" -Force
```

## 각 설정의 이유

| 설정 | 이유 |
|---|---|
| `-Execute`에 conda 절대 경로 | 스케줄러는 PATH가 다르다. `python`이라고 쓰면 base 아나콘다(3.12)가 잡히고, 거기엔 `feedparser`가 없어 실패한다. |
| `-WorkingDirectory` 프로젝트 루트 | `load_dotenv()`가 cwd 기준으로 `.env`를 찾는다. 지정하지 않으면 `GITHUB_TOKEN`을 못 읽어 GitHub 수집기만 조용히 실패한다. |
| `-StartWhenAvailable` | 08:00에 PC가 꺼져 있으면 켜진 뒤 실행한다. 없으면 그날 metrics가 영구히 빈다. |
| `Register-ScheduledTask` (≠ `schtasks`) | `schtasks`에는 작업 디렉토리 지정 옵션이 없다. |

## 확인

```powershell
Start-ScheduledTask -TaskName "AI_Radar_Collect"          # 수동 실행
Get-ScheduledTaskInfo -TaskName "AI_Radar_Collect"        # LastTaskResult 0 이면 성공
```

로그: `logs/collect_YYYY-MM-DD.log`

## 해제

```powershell
Unregister-ScheduledTask -TaskName "AI_Radar_Collect" -Confirm:$false
```
