package com.fastflow.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fastflow.entity.user.User;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface UserMapper extends BaseMapper<User> {
}
