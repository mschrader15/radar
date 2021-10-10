import time
import ctypes
from collections import Counter
from typing import Dict, List
from copy import deepcopy

PATH_TO_DLL = r"C:\Users\gle\Documents\radar\Windows_msvc_2017_x64\iSYS5220_radarAPI.dll"

# Not sure what to use on Ubuntu, but there should be an equivalent ctypes function
# I used windows b.c. couldn't figure out how to connect to CheckPoint VPN on Linux
dll = ctypes.WinDLL(PATH_TO_DLL)

# Map the IP address in list form to a unsigned integer
ip = map(ctypes.c_uint8, [10,252,47,252])


"""-------------- Below Emmulates iSYS5220_radarAPI_structs.h and iSYS5220_radarAPI_enum.h ----------------"""


apiHandle = ctypes.c_uint64()  # This was the tricky one. Looks like a struct in C++ but really just a long HEX


class iSYS5220_TrackClass_u(ctypes.Union):
    _fields_ = [
        ('iSYS5220_TrackClass', ctypes.c_uint32),
        ('dummy', ctypes.c_uint32)
    ]

class iSYS5220_TrackedObject_t(ctypes.Structure):
    _fields_ =[
        ('ui32_objectID', ctypes.c_uint32),
        ('ui16_ageCount', ctypes.c_uint16),
        ('ui16_predictionCount', ctypes.c_uint16),
        ('ui16_staticCount', ctypes.c_uint16),
        ('f32_trackQuality', ctypes.c_float),
        ('classID', iSYS5220_TrackClass_u),
        ('si16_motion_eventZoneIndex', ctypes.c_int16),
        ('si16_presence_eventZoneIndex', ctypes.c_int16),
        ('f32_positionX_m', ctypes.c_float),
        ('f32_positionY_m', ctypes.c_float),
        ('f32_velocityX_mps', ctypes.c_float),
        ('f32_velocityY_mps', ctypes.c_float),
        ('f32_velocityInDir_mps', ctypes.c_float),
        ('f32_directionX', ctypes.c_float),
        ('f32_directionY', ctypes.c_float),
        ('f32_distanceToFront_m', ctypes.c_float),
        ('f32_distanceToBack_m', ctypes.c_float),
        ('f32_length_m', ctypes.c_float),
        ('f32_width_m', ctypes.c_float),
    ]

class iSYS5220_ObjectListError_u(ctypes.Union):
    _fields_ = [
        ('iSYS5220_ObjectListError_t', ctypes.c_uint16),
        ('dummy', ctypes.c_uint32)
    ]

class iSYS5220_ObjectList_t(ctypes.Structure):
    _fields_ = [
        ("error", iSYS5220_ObjectListError_u),
        ("f32_rainInterferenceLevel", ctypes.c_float),
        ("nrOfTracks", ctypes.c_uint32),
        ("systemState", ctypes.c_uint32),
        ("reserved2", ctypes.c_uint32),
        ("reserved3", ctypes.c_uint32),
        ("trackedObjects", iSYS5220_TrackedObject_t * 256)
    ]

    def __init__(self, *args, **kw) -> None:
        elems = (ctypes.POINTER(iSYS5220_TrackedObject_t) * 256)()
        self.STRUCT_ARRAY = ctypes.cast(elems, ctypes.POINTER(iSYS5220_TrackedObject_t))
        super().__init__(*args, **kw)



class ObjLogger:

    FREQ = 50e-3

    def __init__(self, sleep_time) -> None:
        
        self._max_age = (sleep_time / ObjLogger.FREQ) * 20 
        
        # self._last_objs: Dict[int, iSYS5220_TrackedObject_t] = {}
        self._valid_ids = []
        self._cur_objs: List[iSYS5220_TrackedObject_t, ] = []
        self._rm_list: List[int] = []

    def _check_validity(self, obj: iSYS5220_TrackedObject_t, ) -> bool:
        if obj.ui16_ageCount <= self._max_age:
            self._valid_ids.append(obj.ui32_objectID)
            return True
        elif obj.ui32_objectID in self._valid_ids:
            return True
        return False
    
    def update(self, obj_list: List[iSYS5220_TrackedObject_t], num_tracked: int) -> None:
        for obj in obj_list:
            if obj.ui32_objectID:
                if obj.ui32_objectID not in self._rm_list:
                    if num_tracked > 0:
                        if self._check_validity(obj, ):
                            self._cur_objs.append(obj)
                        else:
                            # return an object ID to return
                            self._rm_list.append(obj.ui32_objectID)
                            # return obj.ui32_objectID
                    else:
                        self._rm_list.append(obj.ui32_objectID)
        return self._rm_list
    
    def time_chunk(self, _time: float) -> None:
        rows = []
        for obj in self._cur_objs:
            row = [_time, str(obj.classID.iSYS5220_TrackClass)]
            for attr, _ in obj._fields_:
                if attr != 'classID':
                    row.append(str(getattr(obj, attr)))
            rows.append(row)
        # self._last_objs.update(self._cur_objs)
        self._cur_objs = []
        return rows
        
        
            









if __name__ == "__main__":

    # specify the sleep time
    SLEEP = 0.1

    # create an instance of the apiHandle object
    handle = apiHandle

    # initialize the system, passing the handle by reference
    res = dll.iSYS5220_initSystem(ctypes.byref(handle), *ip)

    # Pull the objects GPS coordinates
    lat = ctypes.c_float()
    lon = ctypes.c_float()
    lat_p = ctypes.pointer(lat)
    lon_p = ctypes.pointer(lon)
    dll.iSYS5220_getGpsCoordinates(handle, lat_p, lon_p)
    print("GPS COORDS ", lat, lon)    


    # create an instance of iSYS5220_ObjectList_t 
    object_list = iSYS5220_ObjectList_t()

    # create the object logger instance
    object_logger = ObjLogger(SLEEP)

    with open('output.csv', 'w') as f:

        f.write(
            ",".join(["epoch_time", "iSYS5220_TrackClass"] + [name for name, _ in iSYS5220_TrackedObject_t._fields_ if name != 'classID']) + "\n"
        )

        # loop and report if there is a tracked vehicle:

        # Need to look for changing age counts. That means it is a car


        while True:
            time_ = str(time.time())
            res = dll.iSYS5220_getObjectList(handle, ctypes.byref(object_list))
            # if object_list.nrOfTracks:
            rm_objs = []
            # for obj in object_list.trackedObjects:
            remove_objs = object_logger.update(object_list.trackedObjects, object_list.nrOfTracks)
            if remove_objs:
                for rm_obj in remove_objs: 
                    res = dll.iSYS5220_removeObject(handle, ctypes.c_uint32(rm_obj))

            f.writelines(
                [
                    ",".join(row) + "\n" for row in object_logger.time_chunk(time_)
                ]
            )
                # rows = []
                # count_ids = Counter(obj.ui32_objectID for obj in object_list.trackedObjects)
                # for obj in object_list.trackedObjects:
                #     if obj.ui32_objectID and (count_ids[obj.ui32_objectID] < 2):
                #         row = [time_, str(obj.classID.iSYS5220_TrackClass)]
                #         for attr, _ in obj._fields_:
                #             if attr != 'classID':
                #                 row.append(str(getattr(obj, attr)))
                #         rows.append(row)
                # f.writelines(
                #     [
                #         ",".join(row) + "\n" for row in rows
                #     ]
                # )

            # x_pos = [(obj.ui32_objectID, obj.ui16_staticCount, obj.f32_positionX_m, obj.f32_positionY_m) for obj in object_list.trackedObjects if obj.f32_positionX_m > 0]
            # print(x_pos)
    
            time.sleep(0.1)

    # try:
    #     except 