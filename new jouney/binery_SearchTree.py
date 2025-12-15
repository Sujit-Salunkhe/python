root=[4,2,7,1,3]
val = 2

class bineryTree:
    def __init__(self,value=0,left=None,right=None),:
        self.key = value
        self.right = right
        self.left = left
def searchBst(self,root,val):
    if not root:
        return None
    if root.val == val:
        return root

    else root.val < val:
            return searchBst(root.right,val)

    return searchBSt(root.left,val)




def insertNode(self,root,val)
    if root is None:
        return binaryTree(val)
    if root > val:
        root.left = insertNode(root.left,val)
    elif:
        root.right = insertNode(root.right,val)
    
    return root
