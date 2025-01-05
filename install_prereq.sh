mkdir pdfs
mkdir secure
mkdir logs
apt-get install -y python3
apt install -y python3-pip
apt install -y libjpeg-turbo
# these commands were required for some time because the normal apt-get command didn't work
# wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb
# sudo apt install -y ./wkhtmltox_0.12.6-1.focal_amd64.deb
sudo apt-get -y install wkhtmltopdf
sudo apt-get -y install postgresql
pip3 install cherrypy --break-system-packages
pip3 install python-dateutil --break-system-packages
pip3 install jinja2
pip3 install requests
pip3 install pdfkit
pip3 install sqlalchemy
pip3 install twilio
pip3 install psycopg2-binary --break-system-packages
pip3 install slack_bolt --break-system-packages

apt install -y python3-jinja2
apt install -y python3-requests
apt install -y python3-pdfkit
apt install -y python3-sqlalchemy
apt install -y python3-twilio

apt-get update
sudo apt install -y certbot
apt-get install software-properties-common
add-apt-repository universe
add-apt-repository ppa:certbot/certbot
apt-get update
certbot certonly --standalone