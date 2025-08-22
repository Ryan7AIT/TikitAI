from services.vector_service import get_vector_service

vs = get_vector_service()
# delete all documents from vector store
vs.reset_vector_store()  # ⚠️ This wipes disk files AND memory
# load documents from data folder
# vs.load_documents_from_data_folder()
# get vector store info
print(vs.get_vector_store_info())