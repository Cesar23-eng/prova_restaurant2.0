' Abre la caja de PROVA sin ninguna ventana de consola.
' Uso: doble clic en este archivo (o crea un acceso directo en el escritorio).
Option Explicit

Dim fso, shell, carpeta, pythonw, mainPy

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

carpeta = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = carpeta & "\.venv\Scripts\pythonw.exe"
mainPy = carpeta & "\main.py"

If Not fso.FileExists(pythonw) Then
    MsgBox "No se encontro el entorno .venv en:" & vbCrLf & carpeta & vbCrLf & vbCrLf & _
           "Crealo una vez desde la terminal del proyecto:" & vbCrLf & _
           "  python -m venv .venv" & vbCrLf & _
           "  .venv\Scripts\python.exe -m pip install -r requirements.txt", _
           vbExclamation, "PROVA"
    WScript.Quit 1
End If

shell.CurrentDirectory = carpeta
' 0 = ventana oculta, False = no esperar a que se cierre la app
shell.Run """" & pythonw & """ """ & mainPy & """", 0, False
