import requests

API_TOKEN = "pk_55274075_8ZKU4012EPJIQB8HMIGH80CFVI95WBD5"
team_id = "90121026186"
space_id = "90124261998"
list_id = "901210697540"
task_id = "8699ja7ha"
headers = {
    "Authorization": API_TOKEN,
}

def get_teams():
    url = "https://api.clickup.com/api/v2/team"
    response = requests.get(url, headers=headers)
    return response.json()

def get_spaces(team_id):
    url = f"https://api.clickup.com/api/v2/team/{team_id}/space"
    response = requests.get(url, headers=headers)
    return response.json()

def get_folders(space_id):
    url = f"https://api.clickup.com/api/v2/space/{space_id}/folder"
    response = requests.get(url, headers=headers)
    return response.json()

def get_folderless_lists(space_id):
    url = f"https://api.clickup.com/api/v2/space/{space_id}/list"
    response = requests.get(url, headers=headers)
    return response.json()


def get_tasks(list_id):
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task?include_closed=true"
    response = requests.get(url, headers=headers)
    return response.json()

def get_task_comments(task_id):
    url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
    response = requests.get(url, headers=headers)
    return response.json()


print(get_teams())