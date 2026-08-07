"""doc 内置库。"""


def build_doc_lib(interp):
    def delete(obj):
        interp.destructor.delete_object(obj)

    def delete_all():
        interp.destructor.delete_all("all")

    def delete_script_created():
        interp.destructor.delete_all("created")

    def find(name):
        for obj in interp.doc.objects:
            if getattr(obj, "script_name", None) == name:
                return obj

            if getattr(obj, "name", None) == name:
                return obj

        return None

    return {
        "delete": delete,
        "delete_all": delete_all,
        "delete_script_created": delete_script_created,
        "find": find,
    }