@echo off
echo Criando ambiente virtual...
py -m venv venv
call venv\Scripts\activate.bat

echo Atualizando pip...
python -m pip install --upgrade pip

echo Instalando Dlib (pre-compilado para evitar erros de C++)...
pip install dlib-19.24.1-cp311-cp311-win_amd64.whl

echo Instalando demais dependencias do projeto...
pip install -r requirements.txt

echo.
echo Instalacao concluida!
echo Para rodar o programa, basta executar o script "iniciar.bat" que vamos criar.
pause
