import pexpect
import subprocess
import os

ACC_NUMBER = os.environ.get("ACC_NUMBER")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
NETWORK_ID = os.environ.get("NETWORK_ID")
#QUERY_TAG = os.environ.get("QUERY_TAG")
#STAKE_AMOUNT = os.environ.get("STAKE_AMOUNT")
#WAIT_PERIOD = os.environ.get("WAIT_PERIOD")
ACC_PWD = os.environ.get("ACC_PWD")
#QUERY_TAG = os.environ.get("QUERY_TAG")
#STAKE_AMOUNT = os.environ.get("STAKE_AMOUNT")
#WAIT_PERIOD = os.environ.get("WAIT_PERIOD")

try:
    cli_process = pexpect.spawn('sh', encoding='utf8', timeout=None)
    cli_process.sendline(f'telliot account add myacct{ACC_NUMBER} {PRIVATE_KEY} {NETWORK_ID}')
    cli_process.expect(f'Enter encryption password for myacct{ACC_NUMBER}:')
    cli_process.sendline(ACC_PWD)
    cli_process.expect(f'Confirm password:')
    cli_process.sendline(ACC_PWD)
    print("Account Created!")

    cli_process.sendline(f'telliot report -a myacct{ACC_NUMBER} -qt validated-feed-usd-spot -ncr --fetch-flex --password {ACC_PWD} --continue-reporting-on-dispute')
    cli_process.expect(': ')
    cli_process.sendline('Y')

    cli_process.logfile = open("/tmp/mylog", "w")
    tail_process = subprocess.Popen(['tail', '-f', '/tmp/mylog'])

    cli_process.expect(f'confirm settings.')
    cli_process.sendline()
    cli_process.sendline()

    # Wait for the process to finish
    cli_process.expect(pexpect.EOF)

except Exception as e:
    print(f"An error occurred: {str(e)}")
finally:
    # Close the pexpect process
    cli_process.close()