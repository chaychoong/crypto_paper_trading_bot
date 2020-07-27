all: deploy clean

package:
	cd .venv/lib/python3.8/site-packages && zip -r9 ${PWD}/function.zip .
	zip -g function.zip lambda_function.py errors.py trade.py
	

deploy: package
	aws lambda update-function-code --function-name ${FUNCTION_NAME} --zip-file fileb://function.zip

clean:
	rm -rf function.zip