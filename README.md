python3 -m venv env
source env/bin/activate

docker build -t heyiming/torrentdownloader .
docker push heyiming/torrentdownloader 